from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from ..permission_middleware import require_permission
from ..database import get_db
from ..models import User, Invoice, InvoiceItem, Product, Warehouse, DiscountCode
from ..schemas_fastapi import InvoiceOut, InvoiceCreate, InvoiceUpdate, InvoiceItemOut
from ..logger import log_info, log_success, log_error, log_warning
from ..services.invoices import update_debt_for_customer
from ..services.discounts import can_use_discount, compute_discount_amount
from ..services.general_diary import create_general_diary_entry
from ..services.auth_helper import get_username_from_request
from ..services.integration_events import emit_event, product_snapshot
from ..cache import cache_get, cache_set, cache_delete_pattern
from datetime import datetime, date


router = APIRouter(prefix="/invoices", tags=["invoices"])

INVOICES_CACHE_KEY = "invoices:list"


@router.get("/")
def list_invoices(
    limit:  int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission('invoices.view')),
):
    cache_key = f"{INVOICES_CACHE_KEY}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    invoices = (
        db.query(Invoice)
        .order_by(Invoice.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [InvoiceOut.model_validate(inv).model_dump() for inv in invoices]
    cache_set(cache_key, result, ttl=60)
    return result


@router.post("/")
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db),
    _: User = Depends(require_permission('invoices.create'))):
    """Tạo hóa đơn mới"""
    log_info("CREATE_INVOICE", f"Tạo hóa đơn mới: {payload.so_hd} - Khách hàng: {payload.nguoi_mua} - Tổng tiền: {payload.tong_tien:,.0f} VND")

    # Chong tao trung: neu client gui lai cung idempotency_key (mang lag tuong
    # request truoc that bai nen bam lai / double-click nut xac nhan thanh toan),
    # tra ve hoa don DA TAO thay vi tao them 1 hoa don moi + tru kho lan 2.
    if payload.idempotency_key:
        existing = db.query(Invoice).filter(Invoice.idempotency_key == payload.idempotency_key).first()
        if existing:
            log_info("CREATE_INVOICE", f"idempotency_key '{payload.idempotency_key}' đã tồn tại — trả về hóa đơn cũ id={existing.id}, không tạo mới")
            return {"success": True, "id": existing.id, "duplicate": True}

    try:
        # Kiểm tra lại mã giảm giá NGAY TẠI SERVER (không tin số tiền client tính) —
        # trước đây trang POS tự lọc/tính giảm giá HOÀN TOÀN ở client (dựa vào
        # discountCodes tải 1 lần lúc load trang + đồng hồ trình duyệt), rồi gửi
        # thẳng tong_tien ĐÃ GIẢM lên đây; endpoint này chưa từng biết/kiểm tra có
        # mã giảm giá nào được dùng — mã đã HẾT HẠN (hoặc chưa tới ngày, đã hết
        # lượt...) vẫn được áp dụng bình thường nếu client cứ gửi tong_tien đã
        # giảm (xác nhận bằng thực nghiệm: gọi thẳng POST /api/invoices/ với 1 mã
        # đã hết hạn không hề bị chặn). .with_for_update() khoá các dòng
        # DiscountCode ngay từ lúc kiểm tra — cùng mẫu chống race đã dùng cho
        # Product/Warehouse — tránh 2 hoá đơn cùng lúc đều "qua" kiểm tra
        # max_uses trước khi bên nào kịp tăng used_count.
        discount_amount_total = 0.0
        discount_amounts_by_id: dict[int, float] = {}
        locked_discount_codes: list[DiscountCode] = []
        if payload.discount_code_ids and payload.items:
            items_subtotal = sum(item.total_price for item in payload.items)
            locked_discount_codes = (
                db.query(DiscountCode)
                .filter(DiscountCode.id.in_(payload.discount_code_ids))
                .with_for_update()
                .all()
            )
            found_ids = {c.id for c in locked_discount_codes}
            missing_ids = set(payload.discount_code_ids) - found_ids
            if missing_ids:
                raise HTTPException(status_code=400, detail=f"Mã giảm giá không tồn tại: {sorted(missing_ids)}")
            for code in locked_discount_codes:
                err = can_use_discount(code, items_subtotal)
                if err:
                    raise HTTPException(status_code=400, detail=f"Mã '{code.code}': {err}")
                amount = compute_discount_amount(code, items_subtotal)
                discount_amounts_by_id[code.id] = amount
                discount_amount_total += amount

        # Tạo hóa đơn mới
        inv = Invoice(
            so_hd=payload.so_hd,
            ngay_hd=payload.ngay_hd,
            nguoi_mua=payload.nguoi_mua,
            customer_id=payload.customer_id,
            idempotency_key=payload.idempotency_key,
            # Có mã giảm giá hợp lệ kèm items -> LUÔN dùng số tiền server tự tính
            # (subtotal từ items trừ giảm giá đã kiểm tra ở trên), không dùng
            # tong_tien client gửi — đóng hoàn toàn đường vòng "tự sửa tong_tien
            # trong request để áp giảm giá tuỳ ý / mã đã hết hạn".
            tong_tien=(
                max(0.0, items_subtotal - discount_amount_total)
                if (payload.discount_code_ids and payload.items) else payload.tong_tien
            ),
            trang_thai=payload.trang_thai,
            hinh_thuc_tt=payload.hinh_thuc_tt,
        )
        db.add(inv)
        db.flush()  # Flush để lấy ID
        
        # Xử lý các items và cập nhật số lượng sản phẩm
        if payload.items:
            # Bước 1: Lock TẤT CẢ sản phẩm cần thiết trước (tránh deadlock bằng cách lock theo thứ tự id)
            product_ids = sorted({item.product_id for item in payload.items if item.product_id})
            locked_products = {
                p.id: p
                for p in db.query(Product)
                    .filter(Product.id.in_(product_ids))
                    .with_for_update()   # SELECT FOR UPDATE — block concurrent transactions
                    .all()
            }

            # Bước 2: Kiểm tra tồn kho đủ không (trước khi ghi bất kỳ thứ gì)
            for item_data in payload.items:
                product = locked_products.get(item_data.product_id)
                if product:
                    available = product.so_luong or 0
                    if available < item_data.so_luong:
                        db.rollback()
                        raise HTTPException(
                            status_code=409,
                            detail=f"Sản phẩm '{item_data.product_name or item_data.product_code}' "
                                   f"chỉ còn {available} cái, không đủ để bán {item_data.so_luong} cái."
                        )

            # Bước 3: Tạo items và trừ kho (đã chắc chắn đủ hàng)
            for item_data in payload.items:
                invoice_item = InvoiceItem(
                    invoice_id=inv.id,
                    product_id=item_data.product_id,
                    product_code=item_data.product_code,
                    product_name=item_data.product_name,
                    so_luong=item_data.so_luong,
                    don_gia=item_data.don_gia,
                    total_price=item_data.total_price
                )
                db.add(invoice_item)

                product = locked_products.get(item_data.product_id)
                if product:
                    current_qty = product.so_luong or 0
                    new_qty = current_qty - item_data.so_luong
                    product.so_luong = new_qty
                    product.trang_thai = 'Còn hàng' if new_qty > 0 else 'Hết hàng'
                    log_info("UPDATE_STOCK", f"Đã cập nhật số lượng sản phẩm {item_data.product_code}: {current_qty} -> {new_qty}")
                    emit_event(db, "stock.changed", "product", product.id, product_snapshot(product))

                # Cập nhật số lượng trong warehouse (nếu có)
                warehouse = db.query(Warehouse).filter(Warehouse.ma_sp == item_data.product_code).with_for_update().first()
                if warehouse:
                    current_wh_qty = warehouse.so_luong or 0
                    new_wh_qty = max(0, current_wh_qty - item_data.so_luong)
                    warehouse.so_luong = new_wh_qty
                    warehouse.trang_thai = 'Còn hàng' if new_wh_qty > 0 else 'Hết hàng'
                    log_info("UPDATE_WAREHOUSE_STOCK", f"Đã cập nhật số lượng kho {warehouse.ma_kho} - SP {item_data.product_code}: {current_wh_qty} -> {new_wh_qty}")

        # Tăng used_count/total_savings CÙNG transaction với việc tạo hoá đơn —
        # nếu đặt ở endpoint /discount-codes/{id}/use riêng (như code cũ) thì
        # POS phải gọi thêm 1 request nữa mới ghi nhận được, dễ bị bỏ qua/lệch
        # nếu request đó thất bại độc lập với hoá đơn.
        for code in locked_discount_codes:
            code.used_count = (code.used_count or 0) + 1
            code.total_savings = (code.total_savings or 0.0) + discount_amounts_by_id.get(code.id, 0.0)

        db.commit()
        db.refresh(inv)
        
        # Cập nhật bảng công nợ
        update_debt_for_customer(db, customer_id=payload.customer_id, customer_name=payload.nguoi_mua)
        
        # Tính tổng số lượng xuất từ các items
        total_quantity_out = sum(item.so_luong for item in payload.items) if payload.items else 0
        
        # Phân biệt nguồn: nếu có items thì từ POS, không có items thì từ Invoice form
        source = "Pos" if payload.items and len(payload.items) > 0 else "Invoice"
        
        # Tự động ghi vào General Diary
        try:
            description = f"{'Bán hàng' if source == 'Pos' else 'Hóa đơn'} {payload.so_hd} - Khách hàng: {payload.nguoi_mua} - Xuất {total_quantity_out} sản phẩm"
            create_general_diary_entry(
                db=db,
                source=source,
                total_amount=payload.tong_tien or 0.0,
                quantity_out=total_quantity_out,
                quantity_in=0,
                description=description
            )
            db.commit()
        except Exception as diary_error:
            db.rollback()
            # Log lỗi nhưng không làm gián đoạn việc tạo invoice
            log_error("CREATE_INVOICE_DIARY", f"Lỗi khi ghi vào General Diary: {str(diary_error)}", error=diary_error)
            # Không rollback vì invoice đã được tạo thành công
        
        cache_delete_pattern("invoices:*")
        cache_delete_pattern("reports:*")
        if payload.items:
            # Tao hoa don tru ton kho san pham — phai xoa cache products:* nguoc lai
            # danh sach san pham se tra ve so_luong cu (stale) toi 5 phut (CACHE_TTL_PRODUCTS)
            cache_delete_pattern("products:*")
        log_success("CREATE_INVOICE", f"Tạo hóa đơn thành công: {payload.so_hd} (ID: {inv.id})")
        return {"success": True, "id": inv.id}
    except IntegrityError as e:
        db.rollback()
        # 2 request gui CUNG idempotency_key that su dong thoi (ca 2 deu vuot qua
        # buoc kiem tra "da ton tai chua" o dau ham truoc khi ben nao commit) —
        # UNIQUE constraint tren idempotency_key chan trung o tang DB. Thay vi
        # tra ve 500 voi loi SQL tho, tra ve dung hoa don ma request kia da tao.
        if payload.idempotency_key and "idempotency_key" in str(e.orig):
            existing = db.query(Invoice).filter(Invoice.idempotency_key == payload.idempotency_key).first()
            if existing:
                log_info("CREATE_INVOICE", f"Đụng độ idempotency_key '{payload.idempotency_key}' — trả về hóa đơn id={existing.id}")
                return {"success": True, "id": existing.id, "duplicate": True}
        log_error("CREATE_INVOICE", f"Lỗi ràng buộc dữ liệu khi tạo hóa đơn {payload.so_hd}", error=e)
        raise HTTPException(status_code=409, detail="Hóa đơn hoặc giao dịch này vừa được xử lý, vui lòng kiểm tra lại danh sách hóa đơn.")
    except HTTPException:
        # BUG da fix: thieu nhanh nay khien MOI HTTPException tu raise ben trong
        # try (vd 409 "khong du hang" o buoc kiem ton kho, va 400 "ma giam gia
        # het han" moi them) bi chinh except Exception ben duoi "nuot" mat — vi
        # HTTPException CUNG LA 1 Exception, khong co nhanh rieng thi no roi
        # thang xuong except Exception, bi boc lai thanh 500 chung chung voi
        # message bi long thong tin sai (da xac nhan bang thuc nghiem: goi
        # invoice vuot ton kho, ky vong 409 nhung nhan ve 500 kem message
        # "Lỗi tạo hóa đơn: 409: Sản phẩm ... " — sai ca status code lan noi
        # dung message). Chi can re-raise nguyen ven o day la du, KHONG duoc de
        # loi xuong except Exception phia duoi.
        db.rollback()
        raise
    except Exception as e:
        log_error("CREATE_INVOICE", f"Lỗi khi tạo hóa đơn {payload.so_hd}", error=e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi tạo hóa đơn: {str(e)}")


@router.put("/{invoice_id:int}")
def update_invoice(invoice_id: int, payload: InvoiceUpdate, request: Request, db: Session = Depends(get_db),
    _: User = Depends(require_permission('invoices.edit'))):
    try:
        inv = db.get(Invoice, invoice_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
        
        # Lấy username từ token
        username = get_username_from_request(request)
        
        # Lưu tên khách hàng cũ để cập nhật công nợ
        old_customer_name = inv.nguoi_mua
        old_customer_id   = inv.customer_id

        # Cập nhật hóa đơn
        if payload.so_hd is not None: setattr(inv, 'so_hd', payload.so_hd)
        if payload.ngay_hd is not None: setattr(inv, 'ngay_hd', payload.ngay_hd)
        if payload.nguoi_mua is not None: setattr(inv, 'nguoi_mua', payload.nguoi_mua)
        if payload.customer_id is not None: setattr(inv, 'customer_id', payload.customer_id)
        if payload.tong_tien is not None: setattr(inv, 'tong_tien', payload.tong_tien)
        if payload.trang_thai is not None: setattr(inv, 'trang_thai', payload.trang_thai)
        if payload.hinh_thuc_tt is not None: setattr(inv, 'hinh_thuc_tt', payload.hinh_thuc_tt)
        
        db.flush()  # Flush để đảm bảo update được thực hiện
        
        # Ghi vào general_diary
        try:
            description_text = f"Sửa hóa đơn: {inv.so_hd} - Khách hàng: {inv.nguoi_mua}"
            create_general_diary_entry(
                db=db,
                source="Invoice",
                total_amount=float(inv.tong_tien or 0),
                quantity_out=0,
                quantity_in=0,
                description=description_text[:255],
                username=username
            )
            db.commit()
        except Exception as diary_error:
            log_error("UPDATE_INVOICE_DIARY", f"Lỗi khi ghi vào General Diary: {str(diary_error)}", error=diary_error)
            db.commit()  # Vẫn commit việc update hóa đơn
        
        # Cập nhật công nợ cho khách hàng cũ (nếu có thay đổi)
        if old_customer_name:
            update_debt_for_customer(db, customer_id=old_customer_id, customer_name=old_customer_name)

        # Cập nhật công nợ cho khách hàng mới
        new_customer_name = payload.nguoi_mua if payload.nguoi_mua is not None else old_customer_name
        new_customer_id    = inv.customer_id
        if new_customer_name and (new_customer_name != old_customer_name or new_customer_id != old_customer_id):
            update_debt_for_customer(db, customer_id=new_customer_id, customer_name=new_customer_name)

        cache_delete_pattern("invoices:*")
        cache_delete_pattern("reports:*")
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật hóa đơn: {str(e)}")


@router.get("/{invoice_id:int}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
    return InvoiceOut.model_validate(inv).model_dump()


@router.get("/{invoice_id:int}/details")
def get_invoice_details(invoice_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết hóa đơn bao gồm các sản phẩm"""
    try:
        inv = db.get(Invoice, invoice_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
        
        # Lấy tất cả items của invoice
        items = []
        try:
            # Kiểm tra xem bảng có tồn tại không bằng cách query
            items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        except Exception as table_error:
            # Nếu bảng chưa tồn tại hoặc có lỗi, log và trả về empty list
            log_warning("GET_INVOICE_DETAILS", f"Có thể bảng invoice_items chưa tồn tại: {str(table_error)}")
            items = []
        
        log_info("GET_INVOICE_DETAILS", f"Lấy chi tiết hóa đơn ID: {invoice_id}, số items: {len(items)}")
        
        # Format date để JSON serializable
        ngay_hd = None
        if inv.ngay_hd:
            if isinstance(inv.ngay_hd, str):
                ngay_hd = inv.ngay_hd
            else:
                ngay_hd = inv.ngay_hd.isoformat()
        
        return {
            "invoice": {
                "id": inv.id,
                "so_hd": inv.so_hd,
                "ngay_hd": ngay_hd,
                "nguoi_mua": inv.nguoi_mua,
                "tong_tien": float(inv.tong_tien) if inv.tong_tien else 0.0,
                "trang_thai": inv.trang_thai
            },
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_code": item.product_code,
                    "product_name": item.product_name,
                    "so_luong": item.so_luong,
                    "don_gia": float(item.don_gia) if item.don_gia else 0.0,
                    "total_price": float(item.total_price) if item.total_price else 0.0
                }
                for item in items
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        log_error("GET_INVOICE_DETAILS", f"Lỗi khi lấy chi tiết hóa đơn {invoice_id}", error=e)
        log_error("GET_INVOICE_DETAILS", f"Chi tiết lỗi: {error_details}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy chi tiết hóa đơn: {str(e)}")


@router.delete("/{invoice_id:int}")
def delete_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db),
    _: User = Depends(require_permission('invoices.delete'))):
    try:
        inv = db.get(Invoice, invoice_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
        
        # Lấy username từ token
        username = get_username_from_request(request)
        
        # Lưu thông tin hóa đơn trước khi xóa
        invoice_info = f"{inv.so_hd} - Khách hàng: {inv.nguoi_mua}"
        customer_name = inv.nguoi_mua
        customer_id   = inv.customer_id
        
        # Xóa hóa đơn
        db.delete(inv)
        db.flush()  # Flush để đảm bảo xóa được thực hiện
        
        # Ghi vào general_diary
        try:
            description_text = f"Xóa hóa đơn: {invoice_info}"
            create_general_diary_entry(
                db=db,
                source="Invoice",
                total_amount=float(inv.tong_tien or 0),
                quantity_out=0,
                quantity_in=0,
                description=description_text[:255],
                username=username
            )
            db.commit()
        except Exception as diary_error:
            log_error("DELETE_INVOICE_DIARY", f"Lỗi khi ghi vào General Diary: {str(diary_error)}", error=diary_error)
            db.commit()  # Vẫn commit việc xóa hóa đơn
        
        # Cập nhật công nợ cho khách hàng
        if customer_name:
            update_debt_for_customer(db, customer_id=customer_id, customer_name=customer_name)

        cache_delete_pattern("invoices:*")
        cache_delete_pattern("reports:*")
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi xóa hóa đơn: {str(e)}")


@router.get("/next-number")
def next_invoice_number(db: Session = Depends(get_db)):
    """Tạo số thứ tự hóa đơn tiếp theo: HĐ-ddmmyy-XXX (001-999).
    Dùng MAX() thay vì .all() để tránh load toàn bảng."""
    today    = date.today()
    date_str = today.strftime("%d%m%y")
    pattern  = f"HĐ-{date_str}-%"

    max_so_hd = db.query(func.max(Invoice.so_hd)).filter(
        Invoice.so_hd.like(pattern)
    ).scalar()

    if not max_so_hd:
        return {"next_number": 1, "date_str": date_str,
                "full_invoice_number": f"HĐ-{date_str}-001"}

    try:
        number_part = max_so_hd.rsplit("-", 1)[-1]
        next_number = min(int(number_part) + 1, 999) if number_part.isdigit() else 1
    except Exception:
        next_number = 1

    return {
        "next_number": next_number,
        "date_str": date_str,
        "full_invoice_number": f"HĐ-{date_str}-{next_number:03d}",
    }


@router.post("/search")
def search_invoices(criteria: dict, db: Session = Depends(get_db)):
    q = db.query(Invoice)
    from_date      = criteria.get("fromDate")
    to_date        = criteria.get("toDate")
    invoice_number = criteria.get("invoiceNumber")
    customer_info  = criteria.get("customerInfo")
    limit          = int(criteria.get("limit", 500))

    if from_date and to_date:
        q = q.filter(Invoice.ngay_hd.between(from_date, to_date))
    if invoice_number:
        q = q.filter(Invoice.so_hd.ilike(f"%{invoice_number}%"))
    if customer_info:
        q = q.filter(Invoice.nguoi_mua.ilike(f"%{customer_info}%"))

    rows = q.order_by(Invoice.id.desc()).limit(limit).all()
    return {"success": True, "data": rows}
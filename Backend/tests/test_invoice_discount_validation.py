"""
Regression test cho cau hoi: "sau khi het thoi gian cua ma giam gia thi neu them
ma giam gia cho hoa don thi co giam hay khong?" — cau tra loi TRUOC KHI SUA la
CO, van giam binh thuong, day la 1 bug that.

Nguyen nhan: toan bo logic loc/tinh giam gia truoc day chi nam o CLIENT (POS
tu loc discountCodes theo dong ho trinh duyet, tu tinh so tien da giam, roi
gui thang tong_tien DA GIAM len POST /api/invoices/). Endpoint tao hoa don
chua bao gio biet/kiem tra co ma giam gia nao duoc dung — da xac nhan bang
thuc nghiem truc tiep qua API (khong qua UI): goi POST /api/invoices/ voi 1
ma giam gia DA HET HAN van thanh cong binh thuong, khong bi chan.

Fix: InvoiceCreate them field discount_code_ids (client gui ID cac ma dang
dung — POS da duoc sua de gui field nay). Server KHOA (.with_for_update(),
tranh race giong Product/Warehouse) + tu kiem tra lai hieu luc bang chinh
services/discounts.py.can_use_discount() (ham nay von da co san, dung cho
endpoint /discount-codes/{id}/use, nhung chua bao gio duoc goi trong luong
tao hoa don that su) — tu choi ro rang neu het han/chua toi ngay/het luot/duoi
don toi thieu. Neu hop le, SERVER tu tinh lai tong_tien (khong tin so client
gui), va tang used_count/total_savings CUNG transaction voi hoa don.
"""
import pytest


def _make_discount_code(db, **overrides):
    from app import models
    defaults = dict(
        code="TESTCODE",
        name="Test Discount",
        discount_type="percentage",
        discount_value=20.0,
        start_date="2020-01-01T00:00:00",
        end_date="2099-01-01T00:00:00",
        min_order_value=0.0,
        status="active",
    )
    defaults.update(overrides)
    code = models.DiscountCode(**defaults)
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


def test_expired_discount_code_rejected_at_invoice_creation(client, auth_headers, sample_product, db):
    from datetime import datetime, timedelta
    expired = _make_discount_code(
        db,
        code="EXPIRED01",
        start_date=(datetime.now() - timedelta(days=60)).isoformat(),
        end_date=(datetime.now() - timedelta(days=30)).isoformat(),
    )

    resp = client.post(
        "/api/invoices/",
        json={
            "so_hd": "TEST-EXPIRED-DISCOUNT",
            "ngay_hd": "2026-01-01",
            "nguoi_mua": "Test Customer",
            "tong_tien": 8000.0,  # client tu y gui so da "giam", server phai bo qua
            "trang_thai": "Đã thanh toán",
            "discount_code_ids": [expired.id],
            "items": [{
                "product_id": sample_product.id,
                "product_code": sample_product.ma_sp,
                "product_name": sample_product.ten_sp,
                "so_luong": 1,
                "don_gia": sample_product.gia_ban,
                "total_price": sample_product.gia_ban,
            }],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "hết hạn" in resp.json()["error"]

    # Khong duoc tao hoa don khi bi tu choi
    from app import models
    inv = db.query(models.Invoice).filter(models.Invoice.so_hd == "TEST-EXPIRED-DISCOUNT").first()
    assert inv is None


def test_valid_discount_code_server_recomputes_total_ignores_client_value(client, auth_headers, sample_product, db):
    valid = _make_discount_code(db, code="VALID01", discount_value=20.0)

    resp = client.post(
        "/api/invoices/",
        json={
            "so_hd": "TEST-VALID-DISCOUNT",
            "ngay_hd": "2026-01-01",
            "nguoi_mua": "Test Customer",
            # Client co tinh gui SAI (khong giam gi ca) — server phai tu tinh lai,
            # khong duoc tin gia tri nay khi discount_code_ids duoc gui kem.
            "tong_tien": sample_product.gia_ban,
            "trang_thai": "Đã thanh toán",
            "discount_code_ids": [valid.id],
            "items": [{
                "product_id": sample_product.id,
                "product_code": sample_product.ma_sp,
                "product_name": sample_product.ten_sp,
                "so_luong": 1,
                "don_gia": sample_product.gia_ban,
                "total_price": sample_product.gia_ban,
            }],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    inv_id = resp.json()["id"]

    from app import models
    inv = db.query(models.Invoice).filter(models.Invoice.id == inv_id).first()
    expected_total = sample_product.gia_ban * 0.8
    assert abs(inv.tong_tien - expected_total) < 0.01, f"expected {expected_total}, got {inv.tong_tien}"

    db.refresh(valid)
    assert valid.used_count == 1
    assert abs(valid.total_savings - sample_product.gia_ban * 0.2) < 0.01


def test_discount_code_max_uses_enforced_at_invoice_creation(client, auth_headers, sample_product, db):
    limited = _make_discount_code(db, code="LIMITED01", discount_type="fixed",
                                   discount_value=1000.0, max_uses=1, used_count=1)

    resp = client.post(
        "/api/invoices/",
        json={
            "so_hd": "TEST-LIMITED-DISCOUNT",
            "ngay_hd": "2026-01-01",
            "nguoi_mua": "Test Customer",
            "tong_tien": sample_product.gia_ban,
            "trang_thai": "Đã thanh toán",
            "discount_code_ids": [limited.id],
            "items": [{
                "product_id": sample_product.id,
                "product_code": sample_product.ma_sp,
                "product_name": sample_product.ten_sp,
                "so_luong": 1,
                "don_gia": sample_product.gia_ban,
                "total_price": sample_product.gia_ban,
            }],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "hết lượt" in resp.json()["error"]


def test_invoice_without_discount_code_ids_unaffected(client, auth_headers, sample_product):
    """Khong gui discount_code_ids (hoa don binh thuong, khong dung ma giam gia)
    van hoat dong nhu truoc — field nay hoan toan optional, khong pha vo luong
    tao hoa don hien co."""
    resp = client.post(
        "/api/invoices/",
        json={
            "so_hd": "TEST-NO-DISCOUNT",
            "ngay_hd": "2026-01-01",
            "nguoi_mua": "Test Customer",
            "tong_tien": sample_product.gia_ban,
            "trang_thai": "Đã thanh toán",
            "items": [{
                "product_id": sample_product.id,
                "product_code": sample_product.ma_sp,
                "product_name": sample_product.ten_sp,
                "so_luong": 1,
                "don_gia": sample_product.gia_ban,
                "total_price": sample_product.gia_ban,
            }],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text


def test_insufficient_stock_returns_409_not_500(client, auth_headers, sample_product):
    """Regression rieng cho bug lien quan phat hien trong luc sua: thieu
    'except HTTPException: raise' khien MOI HTTPException raise trong ham
    create_invoice (kien tra ton kho, va ca validate ma giam gia moi them) bi
    except Exception chung phia duoi 'nuot' mat, boc lai thanh 500 chung
    chung thay vi giu dung status code + message da dinh."""
    resp = client.post(
        "/api/invoices/",
        json={
            "so_hd": "TEST-INSUFFICIENT-STOCK",
            "ngay_hd": "2026-01-01",
            "nguoi_mua": "Test Customer",
            "tong_tien": 999999.0,
            "trang_thai": "Đã thanh toán",
            "items": [{
                "product_id": sample_product.id,
                "product_code": sample_product.ma_sp,
                "product_name": sample_product.ten_sp,
                "so_luong": sample_product.so_luong + 1000,
                "don_gia": sample_product.gia_ban,
                "total_price": 999999.0,
            }],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409, resp.text
    assert "không đủ" in resp.json()["error"]

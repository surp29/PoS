from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# User schemas for authentication
class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: bool

    class Config:
        from_attributes = True


class ProductGroupOut(BaseModel):
    id: int
    ten_nhom: str
    mo_ta: Optional[str] = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    ma_sp: Optional[str] = None
    ten_sp: Optional[str] = None
    nhom_sp: Optional[str] = None  # Đổi từ nhom_id thành nhom_sp
    so_luong: Optional[int] = 0
    gia_ban: Optional[float] = 0
    gia_chung: Optional[float] = None  # Thêm giá chung
    gia_von: Optional[float] = 0.0  # Cost price field
    don_vi: Optional[str] = 'cái'  # Unit field
    trang_thai: Optional[str] = None
    mo_ta: Optional[str] = None
    image_url: Optional[str] = None  # Image URL field

    class Config:
        from_attributes = True


class PriceOut(BaseModel):
    id: int
    ma_sp: str
    ten_sp: str
    gia_chung: float
    ghi_chu: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WarehouseOut(BaseModel):
    id: int
    ma_kho: Optional[str]
    ten_kho: Optional[str]
    dia_chi: Optional[str]
    dien_thoai: Optional[str]
    product_id: Optional[int] = None
    ma_sp: Optional[str]
    gia_nhap: Optional[float]
    so_luong: Optional[int]
    ghi_chu: Optional[str]
    trang_thai: Optional[str]
    # Legacy compatibility fields
    so_luong_sp: Optional[int] = None
    mo_ta: Optional[str] = None
    nhom_san_pham: Optional[str] = None

    class Config:
        from_attributes = True
        
    def model_dump(self, **kwargs):
        """Override to include computed legacy fields"""
        data = super().model_dump(**kwargs)
        if self.so_luong is not None:
            data['so_luong_sp'] = self.so_luong
        if self.ghi_chu is not None:
            data['mo_ta'] = self.ghi_chu
        return data


class ProductGroupUpdate(BaseModel):
    mo_ta: Optional[str] = None


class PriceCreate(BaseModel):
    ma_sp: str
    ten_sp: str
    gia_chung: float
    ghi_chu: Optional[str] = None


class PriceUpdate(BaseModel):
    ma_sp: Optional[str] = None
    ten_sp: Optional[str] = None
    gia_chung: Optional[float] = None
    ghi_chu: Optional[str] = None


class ProductCreate(BaseModel):
    nhom_sp: Optional[str] = None
    ma_sp: Optional[str] = None
    ten_sp: Optional[str] = None
    so_luong: Optional[int] = 0
    gia_ban: Optional[float] = 0
    gia_chung: Optional[float] = None  # Thêm giá chung
    gia_von: Optional[float] = 0.0  # Cost price field
    don_vi: Optional[str] = 'cái'  # Unit field
    trang_thai: Optional[str] = None
    mo_ta: Optional[str] = None
    image_url: Optional[str] = None  # Image URL field
    
    # Frontend compatibility fields
    code: Optional[str] = None  # Alias for ma_sp
    name: Optional[str] = None  # Alias for ten_sp
    group: Optional[str] = None  # Alias for nhom_sp
    cost_price: Optional[float] = None  # Alias for gia_von
    price: Optional[float] = None  # Alias for gia_ban
    quantity: Optional[int] = None  # Alias for so_luong
    unit: Optional[str] = None  # Alias for don_vi
    description: Optional[str] = None  # Alias for mo_ta


class ProductUpdate(BaseModel):
    nhom_sp: Optional[str] = None
    ma_sp: Optional[str] = None
    ten_sp: Optional[str] = None
    so_luong: Optional[int] = None
    gia_ban: Optional[float] = None
    gia_chung: Optional[float] = None
    gia_von: Optional[float] = None  # Cost price field
    don_vi: Optional[str] = None  # Unit field
    trang_thai: Optional[str] = None
    mo_ta: Optional[str] = None
    image_url: Optional[str] = None  # Image URL field
    
    # Frontend compatibility fields
    code: Optional[str] = None  # Alias for ma_sp
    name: Optional[str] = None  # Alias for ten_sp
    group: Optional[str] = None  # Alias for nhom_sp
    cost_price: Optional[float] = None  # Alias for gia_von
    price: Optional[float] = None  # Alias for gia_ban
    quantity: Optional[int] = None  # Alias for so_luong
    unit: Optional[str] = None  # Alias for don_vi
    description: Optional[str] = None  # Alias for mo_ta


class WarehouseCreate(BaseModel):
    ma_kho: str
    ten_kho: str
    dia_chi: str
    dien_thoai: Optional[str] = None
    ma_sp: Optional[str] = None
    gia_nhap: Optional[float] = 0.0
    so_luong: Optional[int] = 0
    so_luong_sp: Optional[int] = 0  # Compatibility field
    trang_thai: Optional[str] = 'Hoạt động'
    nhom_san_pham: Optional[str] = None
    mo_ta: Optional[str] = None  # Compatibility field
    ghi_chu: Optional[str] = None


class WarehouseUpdate(BaseModel):
    ma_kho: Optional[str] = None
    ten_kho: Optional[str] = None
    dia_chi: Optional[str] = None
    dien_thoai: Optional[str] = None
    so_luong_sp: Optional[int] = None
    trang_thai: Optional[str] = None
    nhom_san_pham: Optional[str] = None
    mo_ta: Optional[str] = None
    ma_sp: Optional[str] = None
    gia_nhap: Optional[float] = None
    so_luong: Optional[int] = None
    ghi_chu: Optional[str] = None


# Users
class UserOut(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[bool] = True

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[bool] = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[bool] = None


# Accounts
class AccountOut(BaseModel):
    id: int
    ten_tk: Optional[str]
    ma_khach_hang: Optional[str]
    ngay_sinh: Optional[date]
    email: Optional[str]
    so_dt: Optional[str]
    dia_chi: Optional[str]
    trang_thai: Optional[bool]

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    ten_tk: str
    ma_khach_hang: Optional[str] = None
    ngay_sinh: Optional[date] = None
    email: Optional[str] = None
    so_dt: Optional[str] = None
    dia_chi: Optional[str] = None
    trang_thai: Optional[bool] = True


class AccountUpdate(BaseModel):
    ten_tk: Optional[str] = None
    ma_khach_hang: Optional[str] = None
    ngay_sinh: Optional[date] = None
    email: Optional[str] = None
    so_dt: Optional[str] = None
    dia_chi: Optional[str] = None
    trang_thai: Optional[bool] = None


# Orders
class OrderOut(BaseModel):
    id: int
    ma_don_hang: Optional[str]
    thong_tin_kh: Optional[str]
    customer_id: Optional[int] = None
    sp_banggia: Optional[str]
    ngay_tao: Optional[date]
    ma_co_quan_thue: Optional[str]
    so_luong: Optional[int]
    tong_tien: Optional[float]
    trang_thai: Optional[str]

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    ma_don_hang: str
    thong_tin_kh: str
    customer_id: Optional[int] = None  # FK sang accounts.id, None = khách vãng lai
    sp_banggia: Optional[str] = None
    ngay_tao: Optional[date] = None
    ma_co_quan_thue: Optional[str] = None
    so_luong: Optional[int] = 1
    tong_tien: Optional[float] = 0
    trang_thai: Optional[str] = None


class OrderUpdate(BaseModel):
    ma_don_hang: Optional[str] = None
    thong_tin_kh: Optional[str] = None
    customer_id: Optional[int] = None
    sp_banggia: Optional[str] = None
    ngay_tao: Optional[date] = None
    ma_co_quan_thue: Optional[str] = None
    so_luong: Optional[int] = None
    tong_tien: Optional[float] = None
    trang_thai: Optional[str] = None


class OrderItemCreate(BaseModel):
    order_id: int
    product_id: int
    so_luong: int
    don_gia: Optional[float] = 0
    total_price: Optional[float] = 0


# Invoices
class InvoiceOut(BaseModel):
    id: int
    so_hd: Optional[str]
    ngay_hd: Optional[date]
    nguoi_mua: Optional[str]
    customer_id: Optional[int] = None
    tong_tien: Optional[float]
    trang_thai: Optional[str]
    hinh_thuc_tt: Optional[str] = None

    class Config:
        from_attributes = True


class InvoiceItemCreate(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    so_luong: int
    don_gia: float
    total_price: float


class InvoiceItemOut(BaseModel):
    id: int
    invoice_id: int
    product_id: int
    product_code: str
    product_name: str
    so_luong: int
    don_gia: float
    total_price: float

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    so_hd: str
    ngay_hd: date
    nguoi_mua: str
    customer_id: Optional[int] = None  # FK sang accounts.id, None = khách vãng lai
    idempotency_key: Optional[str] = None  # chống tạo trùng khi client gửi lại
    tong_tien: float
    trang_thai: Optional[str] = 'Đã thanh toán'
    hinh_thuc_tt: Optional[str] = None
    items: Optional[list[InvoiceItemCreate]] = []  # List of invoice items
    # ID các mã giảm giá client claim đã áp dụng (POS gửi lên) — server SẼ TỰ
    # kiểm tra lại hiệu lực (hết hạn/chưa tới ngày/đủ lượt/đủ đơn tối thiểu) và
    # tự tính lại số tiền giảm, KHÔNG tin tong_tien client gửi khi trường này có
    # giá trị. Xem services/discounts.py + api_fastapi/invoices.py create_invoice.
    discount_code_ids: Optional[list[int]] = None


class InvoiceUpdate(BaseModel):
    so_hd: Optional[str] = None
    ngay_hd: Optional[date] = None
    nguoi_mua: Optional[str] = None
    customer_id: Optional[int] = None
    tong_tien: Optional[float] = None
    trang_thai: Optional[str] = None
    hinh_thuc_tt: Optional[str] = None


# Area schemas
class AreaBase(BaseModel):
    name: str
    code: str
    type: str
    province: str
    district: Optional[str] = None
    ward: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"
    priority: str = "medium"

class AreaCreate(AreaBase):
    pass

class AreaUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    type: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class AreaOut(AreaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    shop_count: Optional[int] = 0

    class Config:
        from_attributes = True


# Shop schemas
class ShopBase(BaseModel):
    name: str
    code: str
    area_id: int
    address: str
    phone: Optional[str] = None
    email: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"

class ShopCreate(ShopBase):
    pass

class ShopUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    area_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ShopOut(ShopBase):
    id: int
    created_at: datetime
    updated_at: datetime
    area_name: Optional[str] = None

    class Config:
        from_attributes = True


# Discount Code Schemas
class DiscountCodeBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    discount_type: str  # 'percentage' or 'fixed'
    discount_value: float
    start_date: datetime
    end_date: datetime
    max_uses: Optional[int] = None
    min_order_value: float = 0.0
    status: str = 'active'


class DiscountCodeCreate(DiscountCodeBase):
    pass


class DiscountCodeUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_uses: Optional[int] = None
    min_order_value: Optional[float] = None
    status: Optional[str] = None


class DiscountCodeOut(DiscountCodeBase):
    id: int
    used_count: int = 0
    total_savings: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GeneralDiaryCreate(BaseModel):
    ngay_nhap: Optional[date] = None
    so_hieu: Optional[str] = None
    dien_giai: Optional[str] = None
    so_luong_nhap: Optional[int] = 0
    so_luong_xuat: Optional[int] = 0
    so_tien: Optional[float] = 0

    class Config:
        from_attributes = True


class GeneralDiaryOut(BaseModel):
    id: int
    ngay_nhap: Optional[date] = None
    so_hieu: Optional[str] = None
    dien_giai: Optional[str] = None
    so_luong_nhap: Optional[int] = 0
    so_luong_xuat: Optional[int] = 0
    so_tien: Optional[float] = 0

    class Config:
        from_attributes = True


# Schedules
class ScheduleOut(BaseModel):
    id: int
    employee_id: int
    work_date: date
    shift_type: str
    notes: Optional[str] = None
    employee_name: Optional[str] = None  # For display purposes
    
    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    employee_id: int
    work_date: date
    shift_type: str
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    employee_id: Optional[int] = None
    work_date: Optional[date] = None
    shift_type: Optional[str] = None
    notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION (POS ↔ Ecommerce)
# ══════════════════════════════════════════════════════════════════════════════

class IntegrationOrderItem(BaseModel):
    sku: str            # khớp Product.ma_sp
    quantity: int
    unit_price: float


class IntegrationCustomer(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class IntegrationOrderCreate(BaseModel):
    # Bắt buộc — khóa idempotency. Ecommerce Backend gửi = số đơn hàng của chính nó
    # (vd "ECOM-000123"). Gọi lại với cùng external_ref sẽ trả về đơn đã tạo trước đó,
    # không tạo mới / không trừ kho lần 2.
    external_ref: str
    customer: IntegrationCustomer
    items: list[IntegrationOrderItem]
    total_amount: Optional[float] = None   # None = tự tính từ items
    payment_method: Optional[str] = None   # 'cod' | 'momo'
    note: Optional[str] = None


class IntegrationOrderOut(BaseModel):
    id: int
    ma_don_hang: str
    external_ref: Optional[str] = None
    trang_thai: str
    tong_tien: float
    customer_id: Optional[int] = None
    created: bool   # True nếu vừa tạo mới, False nếu trả về đơn đã tồn tại (idempotent replay)


class IntegrationOrderItemOut(BaseModel):
    sku: str
    quantity: int
    unit_price: float
    total_price: float
    returned_qty: int


class IntegrationOrderDetailOut(BaseModel):
    id: int
    ma_don_hang: str
    external_ref: Optional[str] = None
    trang_thai: str
    tong_tien: float
    source: str
    items: list[IntegrationOrderItemOut]


class IntegrationEventOut(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: Optional[str] = None
    payload: dict
    created_at: datetime

    class Config:
        from_attributes = True


class IntegrationReturnItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0)


class IntegrationReturnCreate(BaseModel):
    # Bắt buộc — khóa idempotency riêng cho lượt trả hàng (khác external_ref của
    # đơn gốc, vì 1 đơn có thể có nhiều lượt trả hàng khác nhau theo thời gian).
    return_ref: str
    items: list[IntegrationReturnItem]


class IntegrationReturnOut(BaseModel):
    id: int
    order_id: int
    return_ref: str
    refund_amount: float
    created: bool  # True nếu vừa xử lý, False nếu trả về kết quả cũ (idempotent replay)
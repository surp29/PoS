'use strict';

/* ═══════════════════════════════════════════════
   PosPos Frontend quản trị — GSAP animation layer dùng chung
   Cùng phong cách với Landing/js/gsap-animations.js (power-out easing,
   stagger nhẹ, tôn trọng prefers-reduced-motion). Chỉ CỘNG THÊM chuyển
   động — không thay chức năng: nếu GSAP không load được (CDN chặn, offline)
   mọi thứ vẫn hoạt động y như trước, chỉ là không có animation.
   ═══════════════════════════════════════════════ */

(function () {
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasGsap = typeof gsap !== 'undefined';

  function markShown() {
    document.documentElement.classList.add('anim-shown');
  }

  // An toàn tuyệt đối: dù animation có chạy hay lỗi giữa chừng, sau 1.5s luôn
  // đảm bảo content-header/content-body hiện ra (khớp với CSS trong style.css).
  setTimeout(markShown, 1500);

  if (reduceMotion || !hasGsap) {
    markShown();
    return;
  }

  // ── 1) Page entrance: header + block đầu tiên của content-body ──────────
  document.addEventListener('DOMContentLoaded', function () {
    var header = document.querySelector('.content-header');
    var body = document.querySelector('.content-body');
    var navItems = document.querySelectorAll('.sidebar-nav > ul > li');

    var tl = gsap.timeline({
      defaults: { ease: 'power3.out' },
      onComplete: markShown,
    });

    // Dùng fromTo (không phải from) cho header/body: style.css ép các phần tử
    // này opacity:0 qua class .js-anim cho tới khi animation xong (chống FOUC
    // nếu JS/GSAP lỗi) — nếu dùng .from(), GSAP đọc "giá trị đích" từ computed
    // style hiện tại (đang là 0 do chính CSS đó), nên animate từ 0 -> 0 và
    // phần tử kẹt vô hình vĩnh viễn. fromTo() khai báo rõ đích đến là 1, không
    // phụ thuộc vào CSS đang hiển thị gì lúc animation bắt đầu.
    if (header) {
      tl.fromTo(header,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.5, clearProps: 'opacity,transform' }, 0);
    }
    if (body) {
      // Chỉ animate các block con trực tiếp (card/table-container/form) —
      // tránh đụng vào canvas/modal ẩn bên trong đã có display:none riêng.
      var blocks = Array.prototype.filter.call(body.children, function (el) {
        return window.getComputedStyle(el).display !== 'none';
      });
      tl.set(body, { opacity: 1 }, 0);
      if (blocks.length) {
        tl.fromTo(blocks,
          { opacity: 0, y: 20 },
          { opacity: 1, y: 0, duration: 0.55, stagger: 0.06, clearProps: 'opacity,transform' }, 0.08);
      }
    }
    if (navItems.length) {
      tl.from(navItems, { opacity: 0, x: -10, duration: 0.35, stagger: 0.025 }, 0);
    }

    // Không có gì để animate (trang không extend base.html, vd login.html) —
    // vẫn phải gỡ trạng thái ẩn nếu vì lý do gì đó .js-anim bị bật.
    if (!header && !body) markShown();
  });

  // ── 2) Modal micro-interaction: icon trong modal-header "pop" khi mở ─────
  // Modal đã có animation CSS (overlayFadeIn/modalSlideUp) rất mượt sẵn rồi —
  // chỉ cộng thêm 1 chi tiết nhỏ, không thay đổi cơ chế mở/đóng hiện có
  // (mọi nơi trong code vẫn chỉ toggle style.display = 'flex'/'none').
  function animateModalOpen(modal) {
    var icon = modal.querySelector('.modal-header h3 i');
    if (icon) {
      gsap.from(icon, { scale: 0, rotate: -20, duration: 0.4, ease: 'back.out(2)', delay: 0.08 });
    }
    var fields = modal.querySelectorAll('.form-group, .modal-body > *');
    if (fields.length && fields.length <= 40) {
      gsap.from(fields, {
        opacity: 0, y: 10, duration: 0.32, ease: 'power2.out',
        stagger: { each: 0.025, from: 'start' }, delay: 0.1,
        clearProps: 'opacity,transform',
      });
    }
  }

  // ── 3) Dropdown menu sidebar: mở nhẹ nhàng thay vì "bật" tức thì ─────────
  // QUAN TRỌNG: animation này tự set container.style.height mỗi frame — mà
  // styleObserver bên dưới lại watch đúng thuộc tính 'style' trên toàn subtree.
  // Ban đầu chặn bằng gsap.isTweening(container), nhưng VẪN LẶP VÔ HẠN trên
  // thực tế (đo được ~1259 lần gọi lại/giây, dropdown "nhảy" liên tục — đúng
  // như người dùng báo cáo): clearProps:'height' ở cuối tween tự xóa inline
  // style height, bản thân việc XÓA đó CŨNG là 1 mutation 'style' — nhưng lúc
  // MutationObserver xử lý mutation này (ở microtask kế tiếp), tween đã kết
  // thúc nên isTweening() trả về false, khiến bị hiểu nhầm là 1 lần mở dropdown
  // MỚI và lặp lại vô hạn (cùng gốc rễ với bug đã fix ở KPI count-up bên dưới:
  // dọn cờ chặn quá sớm, trước khi mutation cuối cùng do chính mình gây ra
  // được xử lý xong). Sửa bằng cờ chặn riêng (WeakSet), chỉ gỡ cờ ở
  // setTimeout(fn, 0) — SAU khi MutationObserver đã xử lý xong mutation
  // clearProps đó.
  var openingDropdowns = new WeakSet();
  function animateDropdownOpen(container) {
    if (openingDropdowns.has(container)) return;
    openingDropdowns.add(container);
    var h = container.scrollHeight;
    gsap.fromTo(container,
      { height: 0, opacity: 0 },
      {
        height: h, opacity: 1, duration: 0.28, ease: 'power2.out', clearProps: 'height',
        onComplete: function () {
          setTimeout(function () { openingDropdowns.delete(container); }, 0);
        },
      }
    );
  }

  // ── 4) Bảng dữ liệu: hàng mới render (fetch xong, đổi trang, tìm kiếm...)
  //      tự động stagger-in — không cần sửa từng trang gọi thủ công.
  function animateNewRows(addedRows) {
    if (!addedRows.length) return;
    gsap.from(addedRows, {
      opacity: 0, y: 8, duration: 0.32, ease: 'power2.out',
      stagger: { each: 0.02, from: 'start' }, clearProps: 'opacity,transform',
    });
  }

  // Một MutationObserver duy nhất, dùng chung cho cả 3 việc trên — tránh mỗi
  // trang phải tự gắn observer riêng.
  var styleObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      var el = m.target;
      if (!(el instanceof HTMLElement)) return;
      if (el.classList.contains('modal-overlay')) {
        if (el.style.display === 'flex') animateModalOpen(el);
        return;
      }
      if (el.classList.contains('dropdown-container')) {
        if (el.style.display === 'block') animateDropdownOpen(el);
        return;
      }
    });
  });
  styleObserver.observe(document.body, {
    attributes: true, attributeFilter: ['style'], subtree: true,
  });

  var rowObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      if (!m.addedNodes || !m.addedNodes.length) return;
      var parent = m.target;
      if (!(parent instanceof HTMLElement) || parent.tagName !== 'TBODY') return;
      var rows = Array.prototype.filter.call(m.addedNodes, function (n) {
        return n.nodeType === 1 && n.tagName === 'TR';
      });
      // Bảng lớn (>60 dòng cùng lúc, vd load lần đầu vài trăm sản phẩm) bỏ
      // qua animate để không làm chậm/nhấp nháy — chỉ animate cập nhật nhỏ
      // (thêm 1 dòng, lọc/tìm kiếm ra vài kết quả...).
      if (rows.length && rows.length <= 60) animateNewRows(rows);
    });
  });
  rowObserver.observe(document.body, { childList: true, subtree: true });

  // ── 5) KPI .stat-number: đếm số tăng dần khi trang tự set textContent =====
  // Hầu hết các trang quản trị (products/orders/invoices/warehouse/...) đều
  // fetch dữ liệu rồi gán thẳng el.textContent = số liệu — không trang nào tự
  // viết animation cho việc này. Thêm 1 chỗ dùng chung ở đây để mọi KPI card
  // trong toàn Frontend đều có hiệu ứng đếm số, không cần sửa từng trang.
  var countingEls = new WeakSet();

  // Nhiều trang dùng inline style minmax(150px,1fr) cho .stats-grid (vd
  // orders.html, products.html) — với KPI số dài (doanh thu VNĐ hàng trăm
  // triệu, không có dấu phân cách nghìn ở 1 số trang), số bị vỡ xuống 3 dòng
  // trông rất xấu (xác nhận bằng ảnh chụp thực tế trên orders.html). Thu nhỏ
  // font-size dần tới khi vừa 1 dòng, chỉ cho xuống dòng nếu đã nhỏ hết mức
  // mà vẫn không vừa — sửa 1 chỗ dùng chung cho toàn bộ Frontend thay vì dò
  // từng trang.
  function fitStatNumber(el) {
    el.style.whiteSpace = 'nowrap';
    el.style.fontSize = '';
    var container = el.parentElement;
    if (!container) return;
    var maxWidth = container.clientWidth;
    if (!maxWidth || el.scrollWidth <= maxWidth) return;
    var size = parseFloat(getComputedStyle(el).fontSize);
    var minSize = 13;
    while (el.scrollWidth > maxWidth && size > minSize) {
      size -= 1;
      el.style.fontSize = size + 'px';
    }
    if (el.scrollWidth > maxWidth) {
      el.style.whiteSpace = 'normal';
      el.style.wordBreak = 'break-word';
    }
  }

  function animateStatNumber(el, originalText) {
    if (countingEls.has(el)) return; // bo qua mutation do chinh tween nay gay ra (giong guard dropdown o tren)
    var target = parseInt(originalText.replace(/[^\d-]/g, ''), 10);
    if (isNaN(target) || target <= 0) { fitStatNumber(el); return; }
    var proxy = { val: 0 };
    countingEls.add(el);
    gsap.to(proxy, {
      val: target, duration: 0.8, ease: 'power2.out',
      onUpdate: function () { el.textContent = Math.round(proxy.val); },
      // Luôn phục hồi ĐÚNG chuỗi gốc (không tự ráp lại số + hậu tố) — tránh làm
      // mất định dạng (dấu chấm phân cách nghìn, đơn vị tiền tệ...) nếu trang
      // nào đó set textContent dạng "15.000.000 ₫" thay vì số nguyên thuần.
      onComplete: function () {
        el.textContent = originalText;
        fitStatNumber(el);
        // QUAN TRỌNG: KHÔNG xóa khỏi countingEls ngay — dòng textContent phía
        // trên vừa tạo ra 1 mutation record mới, nhưng statObserver chỉ xử lý
        // mutation đó ở microtask KẾ TIẾP (sau khi hàm này chạy xong). Nếu xóa
        // countingEls ngay tại đây (đồng bộ), lúc statObserver xử lý mutation
        // "phục hồi chuỗi gốc" thì guard đã biến mất, khiến nó tưởng đây là 1
        // lần cập nhật MỚI và khởi động lại đếm từ 0 — tạo vòng lặp vô hạn (đã
        // xác nhận bằng thực nghiệm: totalShops nhảy 0→4 lặp lại mỗi ~0.8s
        // không bao giờ dừng). setTimeout(0) đẩy việc xóa sang macrotask, chạy
        // SAU khi microtask của MutationObserver đã xử lý xong mutation này.
        setTimeout(function () { countingEls.delete(el); }, 0);
      },
    });
  }

  var statObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      var el = m.target;
      if (!(el instanceof HTMLElement) || !el.classList.contains('stat-number')) return;
      if (countingEls.has(el)) return;
      var text = el.textContent.trim();
      if (/^-?[\d.,]+/.test(text)) animateStatNumber(el, text);
      else fitStatNumber(el);
    });
  });
  statObserver.observe(document.body, { childList: true, subtree: true });

  // ── 6) Fit lại .stat-number khi khoảng trống hiển thị đổi kích thước ─────
  // fitStatNumber() ở trên chỉ chạy 1 LẦN lúc gán giá trị — không tự chạy lại
  // khi không gian hiển thị hẹp đi SAU ĐÓ, khiến số bị TRÀN RA NGOÀI card nếu
  // thu nhỏ giao diện lại sau khi đã fit vừa ở lúc rộng hơn (báo cáo thực tế:
  // HTML còn lại white-space:nowrap từ lần fit trước nhưng font-size không co
  // theo, số tràn ra ngoài). Dùng ResizeObserver thay vì lắng nghe 'resize' của
  // window — khoảng trống hiển thị có thể đổi kích thước dù cửa sổ KHÔNG đổi
  // (vd bấm thu gọn sidebar chỉ đổi margin-left qua CSS transition, không bao
  // giờ bắn 'resize'); ResizeObserver bắt đúng mọi trường hợp co giãn layout.
  if ('ResizeObserver' in window) {
    var statResizeObserver = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) {
        var el = entry.target.querySelector('.stat-number');
        if (el) fitStatNumber(el);
      });
    });
    document.querySelectorAll('.stat-content').forEach(function (container) {
      statResizeObserver.observe(container);
    });
  } else {
    // Trình duyệt cũ không có ResizeObserver — fallback nghe window resize
    // (debounce nhẹ, tránh chạy dồn dập lúc kéo thả cửa sổ).
    var resizeTimer = null;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        document.querySelectorAll('.stat-number').forEach(fitStatNumber);
      }, 150);
    });
  }
})();

import asyncio, csv, os, shutil
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# ─── CẤU HÌNH ─────────────────────────────────────────────────────────────
INTERVAL = 300  # giây
USER_DESKTOP = Path.home() / "Desktop"
DEST_DIR = USER_DESKTOP / "Livestream_Reports"
SCREENSHOT_DIR = DEST_DIR / "screenshots"

os.makedirs(DEST_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ─── XPATH CÁC CHỈ SỐ CẦN LẤY ──────────────────────────────────────────────
GMV_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[1]/div[2]"
VIEW_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[1]/div[2]/div[3]/div[2]"
GPM_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[2]/div[2]"
PCU_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[1]/div[2]/div[4]/div[2]"
TONGDONHANG_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[1]/div[2]"
AVGDONHANG_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[2]/div[2]/div"
NGUOIMUA_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[3]/div[2]"
TYLECLICK_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[3]/div[2]"
TYLENHAPCHUOT_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[4]/div[2]"
MATHANGDUOCBAN_XPATH = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[4]/div[2]"

async def decode_scroller(page, xpath) -> int | None:
    js = '''
    (xp) => {
      const root = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
      if (!root) return null;

      const digits = [];
      root.querySelectorAll('.index-module__numberScroller--gHI3g').forEach(s => {
        const hidden = s.querySelector('.index-module__numberWrapHidden--ugWwk')?.textContent.trim();
        if (hidden === ',') return;
        if (hidden === '.') { digits.push('.'); return; }

        const anim = s.querySelector('.index-module__numberAnimation---1dZw');
        if (!anim) return;
        const top = Math.abs(parseFloat(anim.style.top));
        const step = parseFloat(getComputedStyle(s).getPropertyValue('--number-size'));
        const digit = Math.round(top / step) % 10;
        digits.push(String(digit));
      });

      const intText = digits.join('').replace(/\./g, '');
      return intText ? parseInt(intText, 10) : null;
    }
    '''
    return await page.evaluate(js, xpath)

async def capture_dashboard_and_products(page, index, date_str):
    try:
        dash_path = SCREENSHOT_DIR / f"dashboard_tab{index + 1}_{date_str}.png"
        await page.screenshot(path=str(dash_path), full_page=True)
        print(f"📸 Đã chụp dashboard: {dash_path}")

        product_selector = "button[aria-label='Next Page']"
        page_num = 1
        while True:
            prod_path = SCREENSHOT_DIR / f"products_tab{index + 1}_page{page_num}_{date_str}.png"
            await page.screenshot(path=str(prod_path), full_page=True)
            print(f"📸 Sản phẩm tab {index + 1}, trang {page_num}")
            next_btn = await page.query_selector(product_selector)
            if next_btn and await next_btn.is_enabled():
                await next_btn.click()
                await asyncio.sleep(1)
                page_num += 1
            else:
                break
    except Exception as e:
        print(f"❌ Lỗi chụp tab {index + 1}: {e}")

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://creator.shopee.vn")

        print("➡️ Vui lòng đăng nhập và mở các tab dashboard livestream...")
        while True:
            await asyncio.sleep(2)
            dashboard_tabs = [p for p in ctx.pages if "/dashboard/live" in p.url]
            if dashboard_tabs:
                break
        print(f"✅ Đã phát hiện {len(dashboard_tabs)} tab dashboard. Bắt đầu thu thập dữ liệu...\n")

        targets = []
        writers = {}

        try:
            while True:
                now = datetime.now()
                today = now.strftime('%d-%m')

                for p in ctx.pages:
                    if "/dashboard/live" in p.url and p not in targets:
                        idx = len(targets) + 1
                        filename = DEST_DIR / f"SHP_Live_{idx}_{today}.csv"
                        new_file = not filename.exists()
                        f = open(filename, "a", newline="", encoding="utf-8")
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        if new_file:
                            writer.writerow([
                                "Date", "Time", "GMV", "Live Views", "GPM", "PCU",
                                "Tổng Đơn", "AVG/Đơn", "Người Mua", "TỶ LỆ CLICK",
                                "TỶ LỆ NHẤP CHUỘT", "Mặt Hàng Được Bán"
                            ])
                        writers[p] = (writer, f)
                        targets.append(p)
                        print(f"➕ Đã thêm phiên: {filename.name}")

                for i, pg in enumerate(targets):
                    try:
                        metrics = await asyncio.gather(
                            decode_scroller(pg, GMV_XPATH),
                            decode_scroller(pg, VIEW_XPATH),
                            decode_scroller(pg, GPM_XPATH),
                            decode_scroller(pg, PCU_XPATH),
                            decode_scroller(pg, TONGDONHANG_XPATH),
                            decode_scroller(pg, AVGDONHANG_XPATH),
                            decode_scroller(pg, NGUOIMUA_XPATH),
                            decode_scroller(pg, TYLECLICK_XPATH),
                            decode_scroller(pg, TYLENHAPCHUOT_XPATH),
                            decode_scroller(pg, MATHANGDUOCBAN_XPATH)
                        )

                        if None not in metrics:
                            writer, _ = writers[pg]
                            writer.writerow([now.strftime("%d/%m"), now.strftime("%H:%M")] + metrics)
                            print(f"[Tab {i+1}] {now:%H:%M} | GMV: {metrics[0]:,} | Views: {metrics[1]:,} | PCU: {metrics[3]:,}")
                    except Exception as e:
                        print(f"⚠️ Lỗi đọc tab {i+1}: {e}")

                for _, (_, fobj) in writers.items():
                    fobj.flush()
                    try:
                        shutil.copyfile(fobj.name, DEST_DIR / os.path.basename(fobj.name))
                    except Exception as e:
                        print(f"⚠️ Không sao chép được {fobj.name}: {e}")

                await asyncio.sleep(INTERVAL)

        except KeyboardInterrupt:
            print("\n⏹️ Dừng thu thập. Đang chụp dashboard...")
            today = datetime.now().strftime('%d-%m')
            for i, pg in enumerate(targets):
                await capture_dashboard_and_products(pg, i, today)
            print("✅ Hoàn tất.")
            for _, (_, fobj) in writers.items():
                fobj.close()

if __name__ == "__main__":
    asyncio.run(main())

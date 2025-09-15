// MatrixLauncher.c — Matrix-style App Launcher (ícones centrados, sem moldura)
// Build (MSVC, duas etapas):
//   rc /nologo /fo MatrixLauncher.res MatrixLauncher.rc
//   cl /nologo /c /TP /W4 /EHsc /O2 /GL /DUNICODE /D_UNICODE MatrixLauncher.c
//   link /NOLOGO /LTCG MatrixLauncher.obj MatrixLauncher.res ^
//        gdiplus.lib shlwapi.lib ole32.lib comctl32.lib user32.lib gdi32.lib shell32.lib uxtheme.lib dwmapi.lib
//
// Build (1 linha):
//   rc /nologo /fo MatrixLauncher.res MatrixLauncher.rc
//   cl /nologo /TP /W4 /EHsc /O2 /GL /DUNICODE /D_UNICODE MatrixLauncher.c ^
//      /link /LTCG MatrixLauncher.res gdiplus.lib shlwapi.lib ole32.lib comctl32.lib user32.lib gdi32.lib shell32.lib uxtheme.lib dwmapi.lib
//
// apps.cfg (mesma pasta do .exe):
//   Name|ExePath|IconRef|Args
//   IconRef: "#101" / "RES:101" / "101" (só dígitos) OU caminho para PNG.

#ifndef __cplusplus
#error "Compile como C++ (/TP) — este arquivo usa GDI+ (Image, Graphics...)."
#endif

#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#define NOMINMAX
#define _CRT_SECURE_NO_WARNINGS

#include <windows.h>
#include <windowsx.h>
#include <objidl.h>    // IStream
#include <shellapi.h>
#include <shlwapi.h>   // SHCreateMemStream, Path*
#include <commctrl.h>
#include <gdiplus.h>
#include <dwmapi.h>
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>

#pragma comment(lib, "Gdiplus.lib")
#pragma comment(lib, "Shlwapi.lib")
#pragma comment(lib, "Comctl32.lib")
#pragma comment(lib, "Shell32.lib")
#pragma comment(lib, "Gdi32.lib")
#pragma comment(lib, "User32.lib")
#pragma comment(lib, "Ole32.lib")
#pragma comment(lib, "UxTheme.lib")
#pragma comment(lib, "Dwmapi.lib")

// --------- Compat DWM (caso SDK antigo) ----------
#ifndef DWMWA_USE_IMMERSIVE_DARK_MODE
#define DWMWA_USE_IMMERSIVE_DARK_MODE 20
#endif
#ifndef DWMWA_WINDOW_CORNER_PREFERENCE
#define DWMWA_WINDOW_CORNER_PREFERENCE 33
#endif
#ifndef DWMWCP_ROUND
#define DWMWCP_ROUND 2
#endif
#ifndef DWMWA_SYSTEMBACKDROP_TYPE
#define DWMWA_SYSTEMBACKDROP_TYPE 38
#endif
#ifndef DWMSBT_MAINWINDOW
#define DWMSBT_MAINWINDOW 2
#endif

// ---------------------- Config ----------------------
#define MAX_APPS            256
#define APP_NAME_MAX        128
#define PATH_MAX_LEN        1024
#define LOG_FILE_NAME       L"MatrixLauncher.log"
#define CONFIG_FILE_NAME    L"apps.cfg"
#define TIMER_ANIM_ID       1
#define TIMER_ANIM_MS       16      // ~60 FPS
#define TIMER_HOVER_ID      2
#define TIMER_HOVER_MS      80
#define MAX_COLS            256
#define MAX_FALLERS_PER_COL 2

// Ícones puros, sem card:
static int g_iconBoxPx = 0;   // definido em runtime via dpi
static int g_padPx     = 0;   // espaçamento entre ícones

// ---------------------- Logging ----------------------
static FILE* g_log = NULL;
static void log_open(const wchar_t* baseDir) {
    wchar_t path[PATH_MAX_LEN];
    lstrcpynW(path, baseDir, PATH_MAX_LEN);
    PathAppendW(path, LOG_FILE_NAME);
    g_log = _wfopen(path, L"a, ccs=UTF-8");
}
static void log_close(void) { if (g_log) { fclose(g_log); g_log = NULL; } }
static void logger_info(const wchar_t* fmt, ...) {
    if (!g_log) return; va_list ap; va_start(ap, fmt);
    SYSTEMTIME st; GetLocalTime(&st);
    fwprintf(g_log, L"%04u-%02u-%02u %02u:%02u:%02u.%03u [INFO] ",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    vfwprintf(g_log, fmt, ap); va_end(ap); fputws(L"\n", g_log); fflush(g_log);
}
static void logger_error(const wchar_t* fmt, ...) {
    if (!g_log) return; va_list ap; va_start(ap, fmt);
    SYSTEMTIME st; GetLocalTime(&st);
    fwprintf(g_log, L"%04u-%02u-%02u %02u:%02u:%02u.%03u [ERROR] ",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    vfwprintf(g_log, fmt, ap); va_end(ap); fputws(L"\n", g_log); fflush(g_log);
}

// ---------------------- Data ----------------------
typedef struct AppItem {
    wchar_t name[APP_NAME_MAX];
    wchar_t exe[PATH_MAX_LEN];
    wchar_t args[PATH_MAX_LEN];
    wchar_t iconRef[PATH_MAX_LEN]; // "#101", "RES:101", "101" OU caminho para PNG
    UINT    iconResId;             // >0 se usar recurso
    Gdiplus::Image* icon;          // carregado sob demanda
    RECT  rect;                    // área do ícone (quadrado)
} AppItem;

static AppItem g_apps[MAX_APPS];
static int g_appCount = 0;

static HINSTANCE g_hInst;
static HWND g_hWnd;
static ULONG_PTR g_gdiplusToken = 0;
static HFONT g_hexFont = NULL;
static int g_dpi = 96;
static int g_hoverIndex = -1;
static int g_selectedIndex = -1;

// hover animation (0..1)
static float g_hoverT[MAX_APPS] = {0};

// Backbuffer
static HBITMAP g_memBmp = NULL;
static HDC g_memDC = NULL;
static int g_memW = 0, g_memH = 0;

// Rain
typedef struct RainDrop { float y; float speed; int length; } RainDrop;
typedef struct RainColumn { int x; int glyphH; int activeCount; RainDrop drops[MAX_FALLERS_PER_COL]; } RainColumn;
static RainColumn g_cols[MAX_COLS];
static int g_colCount = 0;
static const wchar_t g_hexChars[] = L"0123456789ABCDEF";

// ---------------------- Utils ----------------------
static int clampi(int v, int a, int b) { return v < a ? a : (v > b ? b : v); }
static float lerp(float a, float b, float t) { return a + (b - a) * t; }
static int dpi_scale(int px) { return MulDiv(px, g_dpi, 96); }

static void create_fonts(void) {
    if (g_hexFont) DeleteObject(g_hexFont);
    LOGFONTW lf = {0};
    lf.lfHeight = -dpi_scale(16); lf.lfWeight = FW_NORMAL; lstrcpyW(lf.lfFaceName, L"Consolas");
    g_hexFont = CreateFontIndirectW(&lf);

    // tamanhos-base
    g_iconBoxPx = dpi_scale(112); // tamanho do quad do ícone
    g_padPx     = dpi_scale(36);  // gap entre ícones
}

static void ensure_backbuffer(HDC hdc, int w, int h) {
    if (w <= 0 || h <= 0) return;
    if (!g_memDC) g_memDC = CreateCompatibleDC(hdc);
    if (!g_memBmp || w != g_memW || h != g_memH) {
        if (g_memBmp) { DeleteObject(g_memBmp); g_memBmp = NULL; }
        g_memBmp = CreateCompatibleBitmap(hdc, w, h);
        g_memW = w; g_memH = h;
    }
}

static void get_exe_dir(wchar_t* outDir, size_t cch) {
    wchar_t path[PATH_MAX_LEN]; GetModuleFileNameW(NULL, path, PATH_MAX_LEN);
    PathRemoveFileSpecW(path); lstrcpynW(outDir, path, (int)cch);
}

static void expand_and_fix_path(const wchar_t* baseDir, const wchar_t* in, wchar_t* out, size_t cch) {
    wchar_t tmp[PATH_MAX_LEN]; ExpandEnvironmentStringsW(in, tmp, PATH_MAX_LEN);
    if (PathIsRelativeW(tmp)) { lstrcpynW(out, baseDir, (int)cch); PathAppendW(out, tmp); }
    else { lstrcpynW(out, tmp, (int)cch); }
    PathCanonicalizeW(out, out);
}

static void strip_crlf(wchar_t* s) {
    size_t len = wcslen(s);
    while (len && (s[len-1] == L'\r' || s[len-1] == L'\n')) s[--len] = 0;
}

// Token -> recurso (#101/RES:101/"101") ou caminho
static void parse_iconref(const wchar_t* baseDir, const wchar_t* tok,
                          wchar_t* outPath, size_t cch, UINT* outResId) {
    outPath[0] = 0; *outResId = 0;
    if (!tok || !*tok) return;
    while (*tok == L' ' || *tok == L'\t') tok++;

    if (tok[0] == L'#') { *outResId = (UINT)wcstoul(tok + 1, NULL, 10); return; }
    if (!_wcsnicmp(tok, L"RES:", 4) || !_wcsnicmp(tok, L"RID:", 4)) {
        *outResId = (UINT)wcstoul(tok + 4, NULL, 10); return;
    }
    bool alldigits = true; for (const wchar_t* p = tok; *p; ++p) {
        if (*p < L'0' || *p > L'9') { alldigits = false; break; }
    }
    if (alldigits) { *outResId = (UINT)wcstoul(tok, NULL, 10); return; }

    expand_and_fix_path(baseDir, tok, outPath, cch);
}

static void parse_config_line(const wchar_t* baseDir, wchar_t* line) {
    if (g_appCount >= MAX_APPS) return;
    strip_crlf(line);
    if (!*line) return;
    if (line[0] == L'#' || (line[0] == L'/' && line[1] == L'/')) return;

    // Name|ExePath|IconRef|Args
    const int MAXTOK = 4; wchar_t* tok[MAXTOK] = {0}; wchar_t* p = line;
    for (int i = 0; i < MAXTOK; ++i) { tok[i] = p; wchar_t* bar = wcschr(p, L'|'); if (bar) { *bar = 0; p = bar + 1; } else break; }

    AppItem* it = &g_apps[g_appCount]; ZeroMemory(it, sizeof(*it));
    if (tok[0]) lstrcpynW(it->name, tok[0], APP_NAME_MAX);
    if (tok[1]) expand_and_fix_path(baseDir, tok[1], it->exe, PATH_MAX_LEN);
    if (tok[2]) parse_iconref(baseDir, tok[2], it->iconRef, PATH_MAX_LEN, &it->iconResId);
    if (tok[3]) lstrcpynW(it->args, tok[3], PATH_MAX_LEN);
    if (it->name[0] && it->exe[0]) g_appCount++;
}

static void load_config(void) {
    wchar_t dir[PATH_MAX_LEN]; get_exe_dir(dir, PATH_MAX_LEN);
    log_open(dir); logger_info(L"Start MatrixLauncher at: %ls", dir);

    wchar_t cfg[PATH_MAX_LEN]; lstrcpynW(cfg, dir, PATH_MAX_LEN); PathAppendW(cfg, CONFIG_FILE_NAME);
    FILE* f = _wfopen(cfg, L"r, ccs=UTF-8");
    if (!f) {
        logger_error(L"Config not found: %ls — creating sample.", cfg);
        FILE* o = _wfopen(cfg, L"w, ccs=UTF-8");
        if (o) {
            fwprintf(o, L"# apps.cfg — Name|ExePath|IconRef|Args\n");
            fwprintf(o, L"Chatbot AI|.\\apps\\ChatbotAI.exe|#101|\n");
            fwprintf(o, L"OCR Tool|.\\apps\\OCRTesseract.exe|.\\resources\\data_ai.png|\n");
            fwprintf(o, L"Task Dashboard|.\\apps\\TaskDesk.exe|#103|\n");
            fclose(o);
        }
        return;
    }
    wchar_t line[4096]; while (fgetws(line, 4096, f)) parse_config_line(dir, line);
    fclose(f); logger_info(L"Loaded %d apps from %ls", g_appCount, cfg);
}

static void unload_icons(void) {
    for (int i = 0; i < g_appCount; ++i) { if (g_apps[i].icon) { delete g_apps[i].icon; g_apps[i].icon = NULL; } }
}

// PNG via recurso (RT_RCDATA ou tipo "PNG")
static Gdiplus::Image* load_image_from_res(UINT resid) {
    HRSRC hRes = FindResourceW(g_hInst, MAKEINTRESOURCEW(resid), RT_RCDATA);
    if (!hRes) hRes = FindResourceW(g_hInst, MAKEINTRESOURCEW(resid), L"PNG");
    if (!hRes) return NULL;
    DWORD sz = SizeofResource(g_hInst, hRes); if (!sz) return NULL;
    HGLOBAL hDat = LoadResource(g_hInst, hRes); if (!hDat) return NULL;
    void* pDat = LockResource(hDat); if (!pDat) return NULL;

    IStream* stm = SHCreateMemStream((const BYTE*)pDat, sz);
    if (!stm) return NULL;
    Gdiplus::Image* img = Gdiplus::Image::FromStream(stm, FALSE);
    stm->Release();
    if (!img || img->GetLastStatus() != Gdiplus::Ok) { if (img) delete img; return NULL; }
    return img;
}

static void ensure_icons_loaded(void) {
    for (int i = 0; i < g_appCount; ++i) {
        if (g_apps[i].icon) continue;
        if (g_apps[i].iconResId > 0) {
            if (Gdiplus::Image* img = load_image_from_res(g_apps[i].iconResId)) {
                g_apps[i].icon = img; logger_info(L"Icon loaded from resource id=%u", g_apps[i].iconResId); continue;
            } else {
                logger_error(L"Failed to load icon from resource id=%u", g_apps[i].iconResId);
            }
        }
        if (g_apps[i].iconRef[0]) {
            if (Gdiplus::Image* img = Gdiplus::Image::FromFile(g_apps[i].iconRef, FALSE)) {
                if (img->GetLastStatus() == Gdiplus::Ok) { g_apps[i].icon = img; logger_info(L"Icon loaded from file: %ls", g_apps[i].iconRef); continue; }
                delete img;
            }
            logger_error(L"Failed to load icon file: %ls", g_apps[i].iconRef);
        }
    }
}

// ---------------------- Layout / Render ----------------------
static void compute_layout_centered(RECT rcClient) {
    const int iconBox = g_iconBoxPx;
    const int pad     = g_padPx;

    int w = rcClient.right - rcClient.left;
    int h = rcClient.bottom - rcClient.top;

    int cols = w / (iconBox + pad); if (cols < 1) cols = 1; if (cols > MAX_COLS) cols = MAX_COLS;
    int rows = (g_appCount + cols - 1) / cols; if (rows < 1) rows = 1;

    // Altura total usada pela grade
    int totalH = rows * iconBox + (rows - 1) * pad;
    int y = (h - totalH) / 2; // centraliza vertical

    int idx = 0;
    for (int r = 0; r < rows && idx < g_appCount; ++r) {
        int remaining = g_appCount - idx;
        int rowItems = remaining < cols ? remaining : cols;
        int rowW = rowItems * iconBox + (rowItems - 1) * pad;
        int x = (w - rowW) / 2; // centraliza horizontal a linha

        for (int c = 0; c < rowItems; ++c, ++idx) {
            g_apps[idx].rect.left   = x;
            g_apps[idx].rect.top    = y;
            g_apps[idx].rect.right  = x + iconBox;
            g_apps[idx].rect.bottom = y + iconBox;
            x += iconBox + pad;
        }
        y += iconBox + pad;
    }
}

static void init_rain(RECT rcClient) {
    int w = rcClient.right - rcClient.left, h = rcClient.bottom - rcClient.top;
    HDC hdc = GetDC(g_hWnd); HFONT old = (HFONT)SelectObject(hdc, g_hexFont);
    TEXTMETRICW tm = {0}; GetTextMetricsW(hdc, &tm); SelectObject(hdc, old); ReleaseDC(g_hWnd, hdc);
    int glyphH = tm.tmHeight + tm.tmExternalLeading, colWidth = glyphH;
    g_colCount = w / colWidth; if (g_colCount > MAX_COLS) g_colCount = MAX_COLS;
    for (int i = 0; i < g_colCount; ++i) {
        g_cols[i].x = i * colWidth + colWidth/4; g_cols[i].glyphH = glyphH;
        g_cols[i].activeCount = 1 + (rand() % MAX_FALLERS_PER_COL);
        for (int d = 0; d < g_cols[i].activeCount; ++d) {
            g_cols[i].drops[d].y = -(float)(rand() % h);
            g_cols[i].drops[d].speed = (float)dpi_scale(60 + rand()%120) / 60.0f;
            g_cols[i].drops[d].length = 6 + rand()%14;
        }
    }
}

static void draw_background_gdip(Gdiplus::Graphics* g, int w, int h) {
    using namespace Gdiplus;
    LinearGradientBrush grad(Gdiplus::Point(0,0), Gdiplus::Point(w,h),
                             Color(255, 5, 8, 10), Color(255, 3, 16, 12));
    g->FillRectangle(&grad, 0, 0, w, h);
}

static void draw_rain(HDC dc, int w, int h) {
    (void)w;
    HFONT old = (HFONT)SelectObject(dc, g_hexFont); SetBkMode(dc, TRANSPARENT);
    for (int i = 0; i < g_colCount; ++i) {
        RainColumn* col = &g_cols[i];
        for (int d = 0; d < col->activeCount; ++d) {
            RainDrop* rp = &col->drops[d]; int len = col->glyphH * rp->length;
            for (int j = 0; j < rp->length; ++j) {
                int y = (int)(rp->y - j * col->glyphH);
                if (y < -col->glyphH || y > h + col->glyphH) continue;
                wchar_t ch = g_hexChars[rand() & 0xF];
                int brightness = 90 - j * 5; if (brightness < 20) brightness = 20;
                SetTextColor(dc, RGB(0, clampi(140 + brightness, 0, 255), 0));
                TextOutW(dc, col->x, y, &ch, 1);
            }
            rp->y += rp->speed;
            if (rp->y - len > h + col->glyphH) {
                rp->y = -(float)(rand() % h);
                rp->speed = (float)dpi_scale(60 + rand()%120) / 60.0f;
                rp->length = 6 + rand()%14;
            }
        }
    }
    SelectObject(dc, old);
}

static void draw_icon(Gdiplus::Graphics* gg, int i, RECT rc, BOOL hovered) {
    using namespace Gdiplus;
    gg->SetSmoothingMode(SmoothingModeHighQuality);
    gg->SetInterpolationMode(InterpolationModeHighQualityBicubic);

    float t = g_hoverT[i];                     // 0..1
    float scale = 1.0f + 0.10f * t;            // até +10% no hover
    int iconBox = rc.right - rc.left;

    int drawW = (int)(iconBox * scale);
    int drawH = (int)(iconBox * scale);
    int drawX = rc.left + (iconBox - drawW)/2;
    int drawY = rc.top  + (iconBox - drawH)/2;

    if (g_apps[i].icon) {
        gg->DrawImage(g_apps[i].icon, drawX, drawY, drawW, drawH);
    } else {
        // placeholder simples (sem retângulo/contorno)
        SolidBrush ph(Color(255, 40, 60, 60));
        gg->FillRectangle(&ph, drawX, drawY, drawW, drawH);
    }
}

// ---------------------- Paint / Input / Launch ----------------------
static void paint(HWND hWnd) {
    PAINTSTRUCT ps; HDC hdc = BeginPaint(hWnd, &ps);
    RECT rc; GetClientRect(hWnd, &rc); int w = rc.right - rc.left, h = rc.bottom - rc.top;
    ensure_backbuffer(hdc, w, h); HGDIOBJ oldBmp = SelectObject(g_memDC, g_memBmp);
    Gdiplus::Graphics gg(g_memDC);

    draw_background_gdip(&gg, w, h);
    draw_rain(g_memDC, w, h);

    ensure_icons_loaded();
    for (int i = 0; i < g_appCount; ++i) {
        BOOL hov = (i == g_hoverIndex);
        draw_icon(&gg, i, g_apps[i].rect, hov);
    }

    BitBlt(hdc, 0, 0, w, h, g_memDC, 0, 0, SRCCOPY);
    SelectObject(g_memDC, oldBmp);
    EndPaint(hWnd, &ps);
}

static void launch_app(int idx) {
    if (idx < 0 || idx >= g_appCount) return; AppItem* it = &g_apps[idx];
    SHELLEXECUTEINFOW sei; ZeroMemory(&sei, sizeof(sei));
    sei.cbSize = sizeof(sei); sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_DDEWAIT;
    sei.hwnd = g_hWnd; sei.lpVerb = L"open"; sei.lpFile = it->exe; sei.lpParameters = it->args[0] ? it->args : NULL;
    wchar_t wdir[PATH_MAX_LEN]; lstrcpynW(wdir, it->exe, PATH_MAX_LEN); PathRemoveFileSpecW(wdir); sei.lpDirectory = wdir; sei.nShow = SW_SHOWNORMAL;
    logger_info(L"Launching: %ls %ls", it->exe, it->args);
    if (!ShellExecuteExW(&sei)) { DWORD err = GetLastError(); logger_error(L"ShellExecuteEx failed (%lu) for %ls", err, it->exe); MessageBoxW(g_hWnd, L"Falha ao iniciar a aplicação. Verifique o caminho no apps.cfg.", L"Erro", MB_ICONERROR); return; }
    // sem minimizar automaticamente — deixa o usuário decidir
}

static int hit_test_icon(POINT pt) { for (int i = 0; i < g_appCount; ++i) if (PtInRect(&g_apps[i].rect, pt)) return i; return -1; }

// Modern frame: dark mode, cantos arredondados, backdrop (Win11)
static void enable_modern_frame(HWND hwnd) {
    BOOL dark = TRUE; DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &dark, sizeof(dark));
    int corners = DWMWCP_ROUND; DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, &corners, sizeof(corners));
    int backdrop = DWMSBT_MAINWINDOW; DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, &backdrop, sizeof(backdrop));
}

static void update_hover_anim() {
    for (int i = 0; i < g_appCount; ++i) {
        float target = (i == g_hoverIndex) ? 1.0f : 0.0f;
        g_hoverT[i] = lerp(g_hoverT[i], target, 0.20f); // easing ~5 frames
    }
}

static void snap_to_cursor_monitor(HWND hWnd, BOOL useWorkArea) {
    POINT pt; GetCursorPos(&pt);
    HMONITOR hMon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
    MONITORINFO mi; mi.cbSize = sizeof(mi);
    if (!GetMonitorInfoW(hMon, &mi)) return;

    RECT r = useWorkArea ? mi.rcWork : mi.rcMonitor; // rcWork: não cobre a taskbar
    SetWindowPos(hWnd, NULL,
                 r.left, r.top,
                 r.right - r.left, r.bottom - r.top,
                 SWP_NOZORDER | SWP_NOACTIVATE);
}

static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        HDC hdc = GetDC(hWnd); g_dpi = GetDeviceCaps(hdc, LOGPIXELSX); ReleaseDC(hWnd, hdc);
        create_fonts(); enable_modern_frame(hWnd);
        SetTimer(hWnd, TIMER_ANIM_ID,  TIMER_ANIM_MS,  NULL);
        SetTimer(hWnd, TIMER_HOVER_ID, TIMER_HOVER_MS, NULL);
        return 0; }
    case WM_SIZE:  {
        RECT rc; GetClientRect(hWnd, &rc);
        compute_layout_centered(rc); init_rain(rc);
        InvalidateRect(hWnd, NULL, FALSE);
        return 0; }
    case WM_TIMER: {
        if (wParam == TIMER_ANIM_ID) { update_hover_anim(); InvalidateRect(hWnd, NULL, FALSE); }
        else if (wParam == TIMER_HOVER_ID) {
            POINT pt; GetCursorPos(&pt); ScreenToClient(hWnd, &pt);
            int idx = hit_test_icon(pt);
            if (idx != g_hoverIndex) { g_hoverIndex = idx; }
        }
        return 0; }
    case WM_MOUSEMOVE: {
        POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
        int idx = hit_test_icon(pt);
        if (idx != g_hoverIndex) { g_hoverIndex = idx; }
        return 0; }
    case WM_LBUTTONUP: {
        POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
        int idx = hit_test_icon(pt);
        if (idx >= 0) { g_selectedIndex = idx; launch_app(idx); }
        return 0; }
    case WM_KEYDOWN: {
        if (wParam == VK_ESCAPE) PostQuitMessage(0);
        else if ((wParam == VK_RETURN || wParam == VK_SPACE) && g_hoverIndex >= 0) {
            launch_app(g_hoverIndex);
        } else if (wParam == VK_LEFT || wParam == VK_RIGHT || wParam == VK_UP || wParam == VK_DOWN) {
            int next = (g_selectedIndex >= 0 ? g_selectedIndex : 0);
            int cellW = g_iconBoxPx, pad = g_padPx;
            RECT rc; GetClientRect(hWnd, &rc); int width = rc.right - rc.left;
            int cols = width / (cellW + pad); if (cols < 1) cols = 1;
            if (wParam == VK_LEFT)  next = clampi(next - 1, 0, g_appCount - 1);
            if (wParam == VK_RIGHT) next = clampi(next + 1, 0, g_appCount - 1);
            if (wParam == VK_UP)    next = clampi(next - cols, 0, g_appCount - 1);
            if (wParam == VK_DOWN)  next = clampi(next + cols, 0, g_appCount - 1);
            if (next != g_selectedIndex) { g_selectedIndex = next; g_hoverIndex = next; InvalidateRect(hWnd, NULL, FALSE); }
        }
        return 0; }
    case WM_PAINT:   { paint(hWnd); return 0; }
    case WM_DESTROY: {
        KillTimer(hWnd, TIMER_ANIM_ID); KillTimer(hWnd, TIMER_HOVER_ID);
        if (g_hexFont) { DeleteObject(g_hexFont); g_hexFont = NULL; }
        if (g_memBmp) { DeleteObject(g_memBmp); g_memBmp = NULL; }
        if (g_memDC) { DeleteDC(g_memDC); g_memDC = NULL; }
        unload_icons(); PostQuitMessage(0); return 0; }
    }
    return DefWindowProcW(hWnd, msg, wParam, lParam);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, PWSTR lpCmd, int nShow) {
    (void)hPrev; (void)lpCmd;
    g_hInst = hInst;
    Gdiplus::GdiplusStartupInput gi;
    if (Gdiplus::GdiplusStartup(&g_gdiplusToken, &gi, NULL) != Gdiplus::Ok) {
        MessageBoxW(NULL, L"Falha ao iniciar GDI+.", L"Erro", MB_ICONERROR);
        return -1;
    }
    load_config();

    const wchar_t* clsName = L"MatrixLauncherWnd";
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.lpszClassName = clsName;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW+1);
    RegisterClassW(&wc);
    
    DWORD style = WS_POPUP;
    DWORD exstyle = WS_EX_APPWINDOW;

    int winW = dpi_scale(1100), winH = dpi_scale(700);
    HWND hWnd = CreateWindowExW(exstyle, clsName, L"Matrix Launcher",
        style, CW_USEDEFAULT, CW_USEDEFAULT, winW, winH, NULL, NULL, hInst, NULL);
    if (!hWnd) return -2;
    g_hWnd = hWnd;

    snap_to_cursor_monitor(g_hWnd, TRUE);

    ShowWindow(g_hWnd, SW_SHOWNORMAL);
    UpdateWindow(g_hWnd);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    log_close();
    Gdiplus::GdiplusShutdown(g_gdiplusToken);
    return 0;
}


/* apps.cfg exemplo
# Name|ExePath|IconRef|Args
Chatbot AI|.\apps\ChatbotAI.exe|#101|
OCR Tool|.\apps\OCRTesseract.exe|.\resources\data_ai.png|
Task Dashboard|.\apps\TaskDesk.exe|#103|
*/

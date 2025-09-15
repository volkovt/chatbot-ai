// MatrixLauncher.c — Matrix-style App Launcher (radial icons, neon glow, tooltips, keyboard/gamepad, idle pulse)
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
#define _USE_MATH_DEFINES

#include <windows.h>
#include <windowsx.h>
#include <objidl.h>    // IStream
#include <shellapi.h>
#include <shlwapi.h>   // SHCreateMemStream, Path*
#include <commctrl.h>
#include <gdiplus.h>
#include <dwmapi.h>
#include <xinput.h>    // Gamepad (dinâmico via LoadLibrary)
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>
#include <cmath>
#include <algorithm>
#include <memory>
#include <math.h>

using std::min;
using std::max;
using std::unique_ptr;


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
static float g_idlePulseHz = 0.20f; // 0.20 Hz (respiração leve)
static float g_radius_scale = 0.4f;

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
    Gdiplus::Color  neonColor;     // cor média->neon
    BOOL    neonReady;
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

// tempo
static ULONGLONG g_t0 = 0;

// Backbuffer
static HBITMAP g_memBmp = NULL;
static HDC g_memDC = NULL;
static int g_memW = 0, g_memH = 0;

// Gamepad (XInput dinâmico)
typedef DWORD (WINAPI *PFN_XInputGetState)(DWORD, XINPUT_STATE*);
static HMODULE g_hXInput = NULL;
static PFN_XInputGetState pXInputGetState = NULL;
static DWORD g_padLastButtons = 0;

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

static void ensure_icons_loaded(void);

// --- Cor média -> neon -------------------------------------------------------
static Gdiplus::Color make_neon_from_avg(BYTE r, BYTE g, BYTE b) {
    // Eleva saturação e brilho; fixa o canal dominante como base neon.
    BYTE m = (BYTE)max(r, max(g, b));
    if (m < 60) { r = 60; g = 180; b = 90; m = 180; } // fallback esverdeado
    float scale = 255.0f / (m ? m : 1);
    float rr = r * scale, gg = g * scale, bb = b * scale;
    // puxa levemente para tons "neon" (aumenta contraste)
    rr = rr * 0.85f; gg = gg * 0.95f; bb = bb * 0.85f;
    rr = (rr > 255 ? 255 : rr);
    gg = (gg > 255 ? 255 : gg);
    bb = (bb > 255 ? 255 : bb);
    return Gdiplus::Color(255, (BYTE)rr, (BYTE)gg, (BYTE)bb);
}

static void compute_icon_neon_color(AppItem* it) {
    using namespace Gdiplus;
    if (!it || !it->icon || it->neonReady) return;

    UINT w = it->icon->GetWidth(), h = it->icon->GetHeight();
    if (w == 0 || h == 0) { it->neonColor = Color(255, 80, 220, 120); it->neonReady = TRUE; return; }

    // Garante Bitmap ARGB
    Bitmap* srcBmp = dynamic_cast<Bitmap*>(it->icon);
    std::unique_ptr<Bitmap> tmp;
    if (!srcBmp) {
        tmp.reset(new Bitmap(w, h, PixelFormat32bppPARGB));
        Graphics g(tmp.get());
        g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
        g.DrawImage(it->icon, 0, 0, w, h);
        srcBmp = tmp.get();
    }

    Rect r(0, 0, (INT)w, (INT)h);
    BitmapData data;
    if (srcBmp->LockBits(&r, ImageLockModeRead, PixelFormat32bppPARGB, &data) != Ok) {
        it->neonColor = Color(255, 80, 220, 120); it->neonReady = TRUE; return;
    }

    UINT stride = (UINT)data.Stride;
    BYTE* base = (BYTE*)data.Scan0;
    UINT stepX = max<UINT>(1, w / 64), stepY = max<UINT>(1, h / 64);
    unsigned long long sumR = 0, sumG = 0, sumB = 0, count = 0;

    for (UINT y = 0; y < h; y += stepY) {
        BYTE* row = base + y * stride;
        for (UINT x = 0; x < w; x += stepX) {
            BYTE* p = row + x * 4; // BGRA
            BYTE a = p[3]; if (a < 24) continue;
            BYTE bb = p[0], gg = p[1], rr = p[2];
            sumR += rr; sumG += gg; sumB += bb; count++;
        }
    }
    srcBmp->UnlockBits(&data);

    BYTE avgR = count ? (BYTE)(sumR / count) : 80;
    BYTE avgG = count ? (BYTE)(sumG / count) : 220;
    BYTE avgB = count ? (BYTE)(sumB / count) : 120;
    it->neonColor = make_neon_from_avg(avgR, avgG, avgB);
    it->neonReady = TRUE;
}

static void ensure_icons_loaded(void) {
    for (int i = 0; i < g_appCount; ++i) {
        if (!g_apps[i].icon) {
            if (g_apps[i].iconResId > 0) {
                if (Gdiplus::Image* img = load_image_from_res(g_apps[i].iconResId)) {
                    g_apps[i].icon = img; logger_info(L"Icon loaded from resource id=%u", g_apps[i].iconResId);
                } else {
                    logger_error(L"Failed to load icon from resource id=%u", g_apps[i].iconResId);
                }
            } else if (g_apps[i].iconRef[0]) {
                if (Gdiplus::Image* img = Gdiplus::Image::FromFile(g_apps[i].iconRef, FALSE)) {
                    if (img->GetLastStatus() == Gdiplus::Ok) { g_apps[i].icon = img; logger_info(L"Icon loaded from file: %ls", g_apps[i].iconRef); }
                    else { delete img; logger_error(L"Failed status loading icon file: %ls", g_apps[i].iconRef); }
                } else {
                    logger_error(L"Failed to load icon file: %ls", g_apps[i].iconRef);
                }
            }
        }
        if (g_apps[i].icon && !g_apps[i].neonReady) compute_icon_neon_color(&g_apps[i]);
    }
}

// ---------------------- Layout (RADIAL) ----------------------
static void compute_layout_radial(RECT rcClient) {
    const int iconBox = g_iconBoxPx;
    const int pad     = g_padPx;

    int w = rcClient.right - rcClient.left;
    int h = rcClient.bottom - rcClient.top;
    float cx = rcClient.left + w * 0.5f;
    float cy = rcClient.top  + h * 0.5f;

    if (g_appCount <= 0) return;

    float maxR = (float)(min(w, h) * 0.5f) - (iconBox * 0.7f);
    if (maxR < iconBox) maxR = (float)iconBox;

    // Verifica se 1 anel comporta (circunferência/ícones)
    float neededR = (g_appCount * (iconBox + pad)) / (2.0f * (float)M_PI);
    if (neededR <= maxR || g_appCount <= 10) {
        // anel único
        // aplica escala configurável para aproximar/afastar ícones
        float r = max(neededR, maxR * g_radius_scale);
        float a0 = - (float)M_PI_2; // começa no topo
        for (int i = 0; i < g_appCount; ++i) {
            float t = a0 + (2.0f * (float)M_PI) * (float)i / (float)g_appCount;
            int x = (int)(cx + r * cosf(t)) - iconBox / 2;
            int y = (int)(cy + r * sinf(t)) - iconBox / 2;
            g_apps[i].rect = { x, y, x + iconBox, y + iconBox };
        }
    } else {
        // dois anéis (metade fora/metade dentro)
        int outerCount = (g_appCount + 1) / 2;
        int innerCount = g_appCount - outerCount;

        // reduz tamanho dos anéis aplicando a mesma escala
        float rOuter = maxR * g_radius_scale;
        float rInner = rOuter - (iconBox + pad + dpi_scale(42)) * g_radius_scale;
        if (rInner < iconBox) rInner = (float)iconBox;

        float a0 = -(float)M_PI_2;
        for (int i = 0; i < outerCount; ++i) {
            float t = a0 + (2.0f * (float)M_PI) * (float)i / (float)outerCount;
            int x = (int)(cx + rOuter * cosf(t)) - iconBox / 2;
            int y = (int)(cy + rOuter * sinf(t)) - iconBox / 2;
            g_apps[i].rect = { x, y, x + iconBox, y + iconBox };
        }
        float a1 = a0 + (float)M_PI / (float)outerCount; // desfasa para intercalar
        for (int j = 0; j < innerCount; ++j) {
            float t = a1 + (2.0f * (float)M_PI) * (float)j / (float)innerCount;
            int x = (int)(cx + rInner * cosf(t)) - iconBox / 2;
            int y = (int)(cy + rInner * sinf(t)) - iconBox / 2;
            g_apps[outerCount + j].rect = { x, y, x + iconBox, y + iconBox };
        }
    }
}

// ---------------------- Rain / Fundo ----------------------
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

// ---------------------- Glow / Rings / Icons ----------------------
static void draw_neon_glow(Gdiplus::Graphics* gg, const RECT& rc, const Gdiplus::Color& neon, float strength, float scale) {
    using namespace Gdiplus;
    int w = rc.right - rc.left, h = rc.bottom - rc.top;
    int cx = rc.left + w/2, cy = rc.top + h/2;

    float baseR = (float)(max(w, h)) * 0.60f * scale;   // raio do glow
    GraphicsPath path;
    path.AddEllipse((REAL)(cx - baseR), (REAL)(cy - baseR), (REAL)(baseR*2), (REAL)(baseR*2));

    BYTE aCenter = (BYTE)clampi((int)(220 * strength), 0, 255);
    Color cCenter(aCenter, neon.GetR(), neon.GetG(), neon.GetB());
    Color cEdge(0, neon.GetR(), neon.GetG(), neon.GetB());

    PathGradientBrush pgb(&path);
    pgb.SetCenterPoint(Point(cx, cy));
    pgb.SetCenterColor(cCenter);
    INT cnt = 1;
    pgb.SetSurroundColors(&cEdge, &cnt);
    gg->FillPath(&pgb, &path);
}

static void draw_double_ring(Gdiplus::Graphics* gg, const RECT& rc, const Gdiplus::Color& neon, float thickness, float expandOuter) {
    using namespace Gdiplus;
    int w = rc.right - rc.left, h = rc.bottom - rc.top;
    float cx = rc.left + w/2.0f, cy = rc.top + h/2.0f;
    float radOuter = max(w, h) * (0.52f + expandOuter);
    float radInner = max(w, h) * (0.40f + expandOuter*0.6f);

    Pen pen1(Color((BYTE)220, neon.GetR(), neon.GetG(), neon.GetB()), thickness);
    Pen pen2(Color((BYTE)160, neon.GetR(), neon.GetG(), neon.GetB()), thickness * 0.8f);
    pen1.SetAlignment(PenAlignmentCenter); pen2.SetAlignment(PenAlignmentCenter);

    gg->DrawEllipse(&pen1, (REAL)(cx - radOuter), (REAL)(cy - radOuter), (REAL)(radOuter*2), (REAL)(radOuter*2));
    gg->DrawEllipse(&pen2, (REAL)(cx - radInner), (REAL)(cy - radInner), (REAL)(radInner*2), (REAL)(radInner*2));
}

static void draw_icon(Gdiplus::Graphics* gg, int i, RECT rc, BOOL hovered, float globalPulse) {
    using namespace Gdiplus;
    gg->SetSmoothingMode(SmoothingModeHighQuality);
    gg->SetInterpolationMode(InterpolationModeHighQualityBicubic);
    gg->SetCompositingMode(CompositingModeSourceOver);

    // Escala: respiração leve + hover
    float t = g_hoverT[i];                     // 0..1
    float scale = (1.0f + 0.03f * globalPulse) * (1.0f + 0.12f * t);
    int iconBox = rc.right - rc.left;

    int drawW = (int)(iconBox * scale);
    int drawH = (int)(iconBox * scale);
    int drawX = rc.left + (iconBox - drawW)/2;
    int drawY = rc.top  + (iconBox - drawH)/2;

    // Glow: ocioso fraco, hover forte; cor média->neon
    Gdiplus::Color neon = g_apps[i].neonReady ? g_apps[i].neonColor : Color(255, 80, 220, 120);
    float glowStrength = hovered ? 1.0f : 0.30f + 0.20f * (0.5f * (globalPulse + 1.0f)); // ~0.3..0.5 idle
    draw_neon_glow(gg, rc, neon, glowStrength, hovered ? 1.25f : 1.0f);

    // Ícone
    if (g_apps[i].icon) {
        gg->DrawImage(g_apps[i].icon, drawX, drawY, drawW, drawH);
    } else {
        SolidBrush ph(Color(255, 40, 60, 60));
        gg->FillEllipse(&ph, (REAL)drawX, (REAL)drawY, (REAL)drawW, (REAL)drawH);
    }

    // Seleção persistente (anel duplo)
    if (i == g_selectedIndex) {
        float thick = (float)dpi_scale(3);
        draw_double_ring(gg, rc, neon, thick, 0.06f + 0.01f * globalPulse);
    }

    // Hover extra: reforça o anel
    if (hovered) {
        float thick = (float)dpi_scale(2);
        draw_double_ring(gg, rc, neon, thick, 0.02f);
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

    // pulso global (seno em baixa frequência)
    float tSec = (float)((GetTickCount64() - g_t0) * 0.001);
    float pulse = sinf(2.0f * (float)M_PI * g_idlePulseHz * tSec);

    for (int i = 0; i < g_appCount; ++i) {
        BOOL hov = (i == g_hoverIndex);
        draw_icon(&gg, i, g_apps[i].rect, hov, pulse);
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

// ---------------------- Gamepad ----------------------
static void xinput_load(void) {
    if (pXInputGetState) return;
    const wchar_t* dlls[] = { L"xinput1_4.dll", L"xinput9_1_0.dll", L"xinput1_3.dll" };
    for (int i = 0; i < 3 && !pXInputGetState; ++i) {
        g_hXInput = LoadLibraryW(dlls[i]);
        if (g_hXInput) {
            pXInputGetState = (PFN_XInputGetState)GetProcAddress(g_hXInput, "XInputGetState");
            if (!pXInputGetState) { FreeLibrary(g_hXInput); g_hXInput = NULL; }
        }
    }
}

static void gamepad_poll_and_nav(void) {
    if (!pXInputGetState) return;
    XINPUT_STATE st; ZeroMemory(&st, sizeof(st));
    if (pXInputGetState(0, &st) != ERROR_SUCCESS) return;

    WORD btn = st.Gamepad.wButtons;
    WORD changedDown = (WORD)((btn ^ g_padLastButtons) & btn);
    g_padLastButtons = btn;

    auto doNav = [&](WPARAM vk) {
        PostMessageW(g_hWnd, WM_KEYDOWN, vk, 0);
    };

    if (changedDown & XINPUT_GAMEPAD_DPAD_LEFT)  doNav(VK_LEFT);
    if (changedDown & XINPUT_GAMEPAD_DPAD_RIGHT) doNav(VK_RIGHT);
    if (changedDown & XINPUT_GAMEPAD_DPAD_UP)    doNav(VK_UP);
    if (changedDown & XINPUT_GAMEPAD_DPAD_DOWN)  doNav(VK_DOWN);

    if (changedDown & XINPUT_GAMEPAD_A) {
        if (g_hoverIndex >= 0) launch_app(g_hoverIndex);
        else if (g_selectedIndex >= 0) launch_app(g_selectedIndex);
    }
}

// ---------------------- Window helpers ----------------------
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

// ---------------------- WndProc ----------------------
static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        HDC hdc = GetDC(hWnd); g_dpi = GetDeviceCaps(hdc, LOGPIXELSX); ReleaseDC(hWnd, hdc);
        create_fonts(); enable_modern_frame(hWnd);
        g_t0 = GetTickCount64();
        xinput_load();

        SetTimer(hWnd, TIMER_ANIM_ID,  TIMER_ANIM_MS,  NULL);
        SetTimer(hWnd, TIMER_HOVER_ID, TIMER_HOVER_MS, NULL);
        return 0; }
    case WM_SIZE:  {
        RECT rc; GetClientRect(hWnd, &rc);
        compute_layout_radial(rc);
        init_rain(rc);
        InvalidateRect(hWnd, NULL, FALSE);
        return 0; }
    case WM_TIMER: {
        if (wParam == TIMER_ANIM_ID) {
            update_hover_anim();
            gamepad_poll_and_nav();
            InvalidateRect(hWnd, NULL, FALSE);
        } else if (wParam == TIMER_HOVER_ID) {
            POINT pt; GetCursorPos(&pt); ScreenToClient(hWnd, &pt);
            int idx = hit_test_icon(pt);
            if (idx != g_hoverIndex) {
                g_hoverIndex = idx;
            }
        }
        return 0; }
    case WM_MOUSEMOVE: {
        POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
        int idx = hit_test_icon(pt);
        if (idx != g_hoverIndex) {
            g_hoverIndex = idx;
        }
        return 0; }
    case WM_LBUTTONUP: {
        POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
        int idx = hit_test_icon(pt);
        if (idx >= 0) { g_selectedIndex = idx; launch_app(idx); }
        return 0; }
    case WM_KEYDOWN: {
        if (wParam == VK_ESCAPE) PostQuitMessage(0);
        else if ((wParam == VK_RETURN || wParam == VK_SPACE)) {
            int idx = (g_hoverIndex >= 0) ? g_hoverIndex : g_selectedIndex;
            if (idx >= 0) launch_app(idx);
        } else if (wParam == VK_LEFT || wParam == VK_RIGHT || wParam == VK_UP || wParam == VK_DOWN) {
            // Navegação radial: aproximação — move para o ícone mais próximo na direção.
            if (g_appCount <= 0) return 0;
            int current = (g_selectedIndex >= 0) ? g_selectedIndex : (g_hoverIndex >= 0 ? g_hoverIndex : 0);
            RECT rcCur = g_apps[current].rect;
            POINT ccur = { (rcCur.left + rcCur.right)/2, (rcCur.top + rcCur.bottom)/2 };

            int best = current; int bestScore = INT_MAX;
            for (int i = 0; i < g_appCount; ++i) if (i != current) {
                RECT r = g_apps[i].rect;
                POINT p = { (r.left + r.right)/2, (r.top + r.bottom)/2 };
                int dx = p.x - ccur.x, dy = p.y - ccur.y;
                bool dirOK = false;
                if (wParam == VK_LEFT)  dirOK = dx < 0 && abs(dy) < abs(dx) * 2;
                if (wParam == VK_RIGHT) dirOK = dx > 0 && abs(dy) < abs(dx) * 2;
                if (wParam == VK_UP)    dirOK = dy < 0 && abs(dx) < abs(dy) * 2;
                if (wParam == VK_DOWN)  dirOK = dy > 0 && abs(dx) < abs(dy) * 2;
                int score = dx*dx + dy*dy;
                if (dirOK && score < bestScore) { bestScore = score; best = i; }
            }
            if (best == current) { // fallback: próximo índice circular
                if (wParam == VK_LEFT || wParam == VK_UP)  best = (current - 1 + g_appCount) % g_appCount;
                if (wParam == VK_RIGHT || wParam == VK_DOWN) best = (current + 1) % g_appCount;
            }
            if (best != current) {
                g_selectedIndex = best;
                g_hoverIndex = best;
                InvalidateRect(hWnd, NULL, FALSE);
            }
        }
        return 0; }
    case WM_PAINT:   { paint(hWnd); return 0; }
    case WM_DESTROY: {
        KillTimer(hWnd, TIMER_ANIM_ID); KillTimer(hWnd, TIMER_HOVER_ID);
        if (g_hexFont) { DeleteObject(g_hexFont); g_hexFont = NULL; }
        if (g_memBmp) { DeleteObject(g_memBmp); g_memBmp = NULL; }
        if (g_memDC) { DeleteDC(g_memDC); g_memDC = NULL; }
        if (g_hXInput) { FreeLibrary(g_hXInput); g_hXInput = NULL; pXInputGetState = NULL; }
        unload_icons(); PostQuitMessage(0); return 0; }
    }
    return DefWindowProcW(hWnd, msg, wParam, lParam);
}

// ---------------------- WinMain ----------------------
int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, PWSTR lpCmd, int nShow) {
    (void)hPrev; (void)lpCmd; (void)nShow;
    g_hInst = hInst;

    INITCOMMONCONTROLSEX icc = { sizeof(icc), ICC_WIN95_CLASSES | ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&icc);

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
    SetFocus(g_hWnd);

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

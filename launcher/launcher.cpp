#define UNICODE
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <gdiplus.h>
#include <shlwapi.h>
#include <shellapi.h>

#pragma comment(lib, "Gdiplus.lib")
#pragma comment(lib, "Dwmapi.lib")
#pragma comment(lib, "Shlwapi.lib")
#pragma comment(lib, "UxTheme.lib")
#pragma comment(lib, "User32.lib")
#pragma comment(lib, "Gdi32.lib")
#pragma comment(lib, "Msimg32.lib")   // AlphaBlend

using namespace Gdiplus;

// ===== Configs =====
static const wchar_t* APP_TO_RUN = L"chatbotai.exe";
static const wchar_t* EVENT_NAME = L"Local\\CHATBOT_AI_READY";
static const int      WIN_W = 400;
static const int      WIN_H = 400;
static const int      TIMER_ID = 1;
static const int      TIMER_MS = 16; // ~60 FPS
static const int      SPINNER_SIZE = 96;
static const int      SPINNER_THICK = 6;
static const int      ARC_SWEEP_DEG = 320;
static const int      ICON_SIZE = 64;
static const COLORREF BG_COLOR = RGB(10, 10, 14);
static const BYTE     BG_ALPHA = 220; // leve translucidez
static const Color C1(255, 255, 64, 129);  // #FF4081
static const Color C2(255, 124, 77, 255);  // #7C4DFF

static const int MAX_WAIT_MS = 60000;
static int g_elapsedMs = 0;

typedef BOOL (WINAPI *pSetProcessDpiAwarenessContext)(HANDLE);

// ===== Globals =====
static ULONG_PTR g_gdiplusToken;
static int g_angle = 0;
static HANDLE g_hEvent = NULL;
static HICON g_hIconSmall = NULL;

// Interpola cores (0..1)
static Color lerp(const Color& a, const Color& b, float t){
    BYTE r = (BYTE)(a.GetR() + (b.GetR() - a.GetR()) * t);
    BYTE g = (BYTE)(a.GetG() + (b.GetG() - a.GetG()) * t);
    BYTE bl= (BYTE)(a.GetB() + (b.GetB() - a.GetB()) * t);
    BYTE al= (BYTE)(a.GetA() + (b.GetA() - a.GetA()) * t);
    return Color(al, r, g, bl);
}

// Desenha arco “conical-like” em segmentos
static void draw_spinner(Graphics& g, PointF center) {
    g.SetSmoothingMode(SmoothingModeHighQuality);
    float radius = (float)SPINNER_SIZE / 2.0f;
    float startAngle = (float)(-g_angle);
    int segments = 64;
    float segSweep = ARC_SWEEP_DEG / (float)segments;

    for (int i = 0; i < segments; ++i) {
        float t = (float)i / (float)(segments - 1);
        Color col = lerp(C1, C2, t);
        Pen pen(col, (REAL)SPINNER_THICK);
        pen.SetStartCap(LineCapRound);
        pen.SetEndCap(LineCapRound);

        float a0 = startAngle + segSweep * i;
        RectF rect(center.X - radius, center.Y - radius, 2*radius, 2*radius);
        g.DrawArc(&pen, rect, a0, segSweep * 0.92f);
    }
}

static BOOL file_exists(const wchar_t* path) {
    return (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES);
}

static void paint(HWND hWnd) {
    RECT rc; GetClientRect(hWnd, &rc);
    HDC hdc = GetDC(hWnd);
    HDC memDC = CreateCompatibleDC(hdc);
    HBITMAP hbmp = CreateCompatibleBitmap(hdc, rc.right, rc.bottom);
    HGDIOBJ old = SelectObject(memDC, hbmp);

    // Fundo
    HBRUSH bg = CreateSolidBrush(BG_COLOR);
    FillRect(memDC, &rc, bg);
    DeleteObject(bg);

    // GDI+ no buffer
    {
        Graphics g(memDC);
        g.SetSmoothingMode(SmoothingModeHighQuality);

        int pad = 14;
        if (g_hIconSmall) {
            DrawIconEx(memDC, pad, pad, g_hIconSmall, ICON_SIZE, ICON_SIZE, 0, NULL, DI_NORMAL);
        }
        SetBkMode(memDC, TRANSPARENT);
        SetTextColor(memDC, RGB(230, 230, 240));
        int fontSize = 36;
        HFONT hFont = CreateFont(
            fontSize,                // Altura da fonte
            0,                       // Largura média dos caracteres (0 = automático)
            0,                       // Ângulo de escapamento
            0,                       // Ângulo de orientação
            FW_BOLD,                 // Peso da fonte (normal, negrito, etc.)
            FALSE,                   // Itálico
            FALSE,                   // Sublinhado
            FALSE,                   // Tachado
            DEFAULT_CHARSET,         // Conjunto de caracteres
            OUT_TT_PRECIS,           // Precisão de saída
            CLIP_DEFAULT_PRECIS,     // Precisão de recorte
            ANTIALIASED_QUALITY,     // Qualidade
            FF_DONTCARE | DEFAULT_PITCH, // Família e pitch
            L"Segoe UI"              // Nome da fonte
        );
        HGDIOBJ oldF = SelectObject(memDC, hFont);
        const wchar_t* title = L"Iniciando...";
        TextOutW(memDC, pad + ICON_SIZE, pad + ICON_SIZE / 3, title, lstrlenW(title));
        SelectObject(memDC, oldF);

        // Spinner central
        PointF center((rc.right - rc.left) / 2.0f, (rc.bottom - rc.top) / 2.0f + 10.0f);
        draw_spinner(g, center);
    }

    // Rounded corners
    HRGN rgn = CreateRoundRectRgn(0, 0, rc.right, rc.bottom, 26, 26);
    SetWindowRgn(hWnd, rgn, TRUE);

    // AlphaBlend sem literal C99
    BLENDFUNCTION bf;
    bf.BlendOp = AC_SRC_OVER;
    bf.BlendFlags = 0;
    bf.SourceConstantAlpha = BG_ALPHA;
    bf.AlphaFormat = 0;

    BitBlt(hdc, 0, 0, rc.right, rc.bottom, memDC, 0, 0, SRCCOPY);

    SelectObject(memDC, old);
    DeleteObject(hbmp);
    DeleteDC(memDC);
    ReleaseDC(hWnd, hdc);
}

static void center(HWND hWnd) {
    RECT rc; GetWindowRect(hWnd, &rc);
    int w = rc.right - rc.left, h = rc.bottom - rc.top;
    RECT wa; SystemParametersInfo(SPI_GETWORKAREA, 0, &wa, 0);
    int x = wa.left + (wa.right - wa.left - w)/2;
    int y = wa.top  + (wa.bottom - wa.top - h)/2;
    SetWindowPos(hWnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE);
}

static void launch_app() {
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    PathRemoveFileSpecW(exePath);
    PathAppendW(exePath, APP_TO_RUN);

    if (!file_exists(exePath)) return;

    SHELLEXECUTEINFOW sei = {0};
    sei.cbSize = sizeof(sei);
    sei.fMask  = SEE_MASK_NOCLOSEPROCESS;
    sei.lpFile = exePath;
    sei.nShow  = SW_SHOWNORMAL;
    ShellExecuteExW(&sei);
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam){
    switch (msg) {
    case WM_CREATE:
        SetTimer(hWnd, TIMER_ID, TIMER_MS, NULL);
        center(hWnd);
        launch_app();
        return 0;
    case WM_TIMER:
        if (wParam == TIMER_ID) {
            g_angle = (g_angle + 6) % 360;
            g_elapsedMs += TIMER_MS;

            if (g_elapsedMs > MAX_WAIT_MS) {
                PostQuitMessage(0);
                return 0;
            }

            InvalidateRect(hWnd, NULL, FALSE);
            if (g_hEvent && WaitForSingleObject(g_hEvent, 0) == WAIT_OBJECT_0) {
                PostQuitMessage(0);
            }
        }
        return 0;
    case WM_PAINT: {
        PAINTSTRUCT ps; BeginPaint(hWnd, &ps);
        paint(hWnd);
        EndPaint(hWnd, &ps);
        return 0; }
    case WM_DESTROY:
        KillTimer(hWnd, TIMER_ID);
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hWnd, msg, wParam, lParam);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int){
    // DPI aware
    HMODULE hUser32 = LoadLibraryW(L"user32.dll");
    if (hUser32) {
        pSetProcessDpiAwarenessContext SetDpiAwareness =
            (pSetProcessDpiAwarenessContext)GetProcAddress(hUser32, "SetProcessDpiAwarenessContext");
        if (SetDpiAwareness) SetDpiAwareness((HANDLE)-4); // PER_MONITOR_AWARE_V2
        FreeLibrary(hUser32);
    }

    // GDI+
    GdiplusStartupInput gpsi;
    GdiplusStartup(&g_gdiplusToken, &gpsi, NULL);

    wchar_t buf[MAX_PATH]; GetModuleFileNameW(NULL, buf, MAX_PATH);
    PathRemoveFileSpecW(buf); PathAppendW(buf, L"resources\\app.ico");
    if (file_exists(buf)) {
        g_hIconSmall = (HICON)LoadImageW(NULL, buf, IMAGE_ICON, ICON_SIZE, ICON_SIZE, LR_LOADFROMFILE);
    }

    // Evento para encerrar
    g_hEvent = CreateEventW(NULL, TRUE, FALSE, EVENT_NAME);

    WNDCLASSW wc = {0};
    wc.style = CS_HREDRAW | CS_VREDRAW | CS_DBLCLKS;
    wc.hInstance = hInst;
    wc.lpszClassName = L"ChatBotAILoader";
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.lpfnWndProc = WndProc;
    RegisterClassW(&wc);

    HWND hWnd = CreateWindowExW(WS_EX_LAYERED | WS_EX_TOPMOST,
        wc.lpszClassName, L"", WS_POPUP,
        CW_USEDEFAULT, CW_USEDEFAULT, WIN_W, WIN_H,
        NULL, NULL, hInst, NULL);

    ShowWindow(hWnd, SW_SHOWNOACTIVATE);
    UpdateWindow(hWnd);
    SetLayeredWindowAttributes(hWnd, 0, BG_ALPHA, LWA_ALPHA);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    if (g_hIconSmall) DestroyIcon(g_hIconSmall);
    if (g_hEvent) CloseHandle(g_hEvent);
    GdiplusShutdown(g_gdiplusToken);
    return 0;
}

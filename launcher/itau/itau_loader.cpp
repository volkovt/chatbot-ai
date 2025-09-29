// Defina NOMINMAX antes de windows.h para impedir macros max/min
#ifndef NOMINMAX
#define NOMINMAX
#endif

// Opcional: só define UNICODE se não vier por linha de comando
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>
#include <windowsx.h>
#include <vector>
#include <cmath>
#include <algorithm>

#pragma comment(lib, "msimg32.lib") // GradientFill

// ---------- Estilo / Cores ----------
static const COLORREF BG_TOP     = RGB(10, 45, 116);   // #0A2D74
static const COLORREF BG_BOTTOM  = RGB(6, 30, 83);     // #061E53
static const COLORREF BORDER     = RGB(17, 57, 133);   // #113985
static const COLORREF BLOCK_COL  = RGB(255, 194, 14);  // #FFC20E
static const int BADGE_RX        = 42;
static const int PADDING         = 36;

// ---------- Timeline / Grid ----------
static const int   COLS      = 24;   // mais alto = mais suave
static const int   ROWS      = 14;
static const int   STEP_MS   = 14;   // atraso entre blocos (construção)
static const int   HOLD_MS   = 900;
static const int   BREATH_MS = 3400;
static const int   BLOCK_GAP = 2;    // “respiro” dentro da célula

// ---------- Texto ----------
static const wchar_t* TITLE_TEXT = L"Ita\u00FA"; // "Itaú"
static const wchar_t* TITLE_FONT = L"Segoe UI";
static const int      TITLE_PT   = 94;
static const int      TITLE_W    = FW_HEAVY; // ~800

// ---------- Estado global simples (p/ demo) ----------
struct Cell { RECT rc; };
struct AppState {
    std::vector<Cell> cells; // blocos válidos (dentro do texto)
    HRGN textRgn = nullptr;  // região do texto engrossada
    RECT badge;              // retângulo do “cartão”
    int totalBlocks = 0;
    int buildTime   = 0;
    int cycleMs     = 0;
    int elapsedMs   = 0;
} G;

// Util: converte pt para pixels aproximado usando 96dpi
static int PtToPx(int pt, HDC hdc) {
    int dpi = GetDeviceCaps(hdc, LOGPIXELSY);
    return MulDiv(pt, dpi, 72);
}

static void FreeRgn(HRGN& r) { if (r) { DeleteObject(r); r = nullptr; } }

// Engrossa uma HRGN unindo cópias levemente deslocadas (truque GDI)
static HRGN ThickenRegion(HRGN base, int pixels) {
    if (!base) return nullptr;
    HRGN acc = CreateRectRgn(0,0,0,0);
    CombineRgn(acc, base, nullptr, RGN_COPY);
    for (int dx = -pixels; dx <= pixels; ++dx) {
        for (int dy = -pixels; dy <= pixels; ++dy) {
            if (dx == 0 && dy == 0) continue;
            HRGN tmp = CreateRectRgn(0,0,0,0);
            CombineRgn(tmp, base, nullptr, RGN_COPY);
            OffsetRgn(tmp, dx, dy);
            CombineRgn(acc, acc, tmp, RGN_OR);
            DeleteObject(tmp);
        }
    }
    return acc;
}

// Cria região do texto centralizado no badge
static HRGN BuildTextRegion(HDC hdc, const RECT& badge) {
    // Fonte dimensionada ao badge (70–75% da largura)
    int targetW = (badge.right - badge.left) * 3 / 4;
    HFONT hFont = CreateFontW(
        PtToPx(TITLE_PT, hdc), 0, 0, 0,
        TITLE_W, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, VARIABLE_PITCH, TITLE_FONT
    );
    HFONT oldF = (HFONT)SelectObject(hdc, hFont);
    SetBkMode(hdc, TRANSPARENT);

    // Medir tamanho do texto
    SIZE sz = {0,0};
    GetTextExtentPoint32W(hdc, TITLE_TEXT, lstrlenW(TITLE_TEXT), &sz);
    if (sz.cx > 0) {
        // escalar aproximando: ajusta altura em pt conforme alvo
        double scale = (double)targetW / (double)sz.cx;
        int newPt = (int)std::max(8.0, TITLE_PT * scale);
        SelectObject(hdc, oldF); DeleteObject(hFont);
        hFont = CreateFontW(
            PtToPx(newPt, hdc), 0, 0, 0,
            TITLE_W, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, VARIABLE_PITCH, TITLE_FONT
        );
        oldF = (HFONT)SelectObject(hdc, hFont);
        GetTextExtentPoint32W(hdc, TITLE_TEXT, lstrlenW(TITLE_TEXT), &sz);
    }

    // Posicionar no centro vertical (baseline approx)
    int badgeW = badge.right - badge.left;
    int badgeH = badge.bottom - badge.top;
    int x = badge.left + (badgeW - sz.cx) / 2;
    int y = badge.top  + (badgeH + sz.cy) / 2 - sz.cy/6; // leve ajuste baseline

    // Constrói Path -> Region
    BeginPath(hdc);
    TextOutW(hdc, x, y - sz.cy, TITLE_TEXT, lstrlenW(TITLE_TEXT));
    EndPath(hdc);
    HRGN text = PathToRegion(hdc);

    // “Engrossa” 1px: une offsets 8-direções
    HRGN thick = ThickenRegion(text, 1);
    DeleteObject(text);

    SelectObject(hdc, oldF);
    DeleteObject(hFont);
    return thick;
}

// Recalcula grade + blocos válidos (chamar em resize)
static void RebuildLayout(HWND hwnd) {
    RECT rc; GetClientRect(hwnd, &rc);

    // Badge (cartão) dentro do padding
    G.badge = { rc.left + PADDING, rc.top + PADDING, rc.right - PADDING, rc.bottom - PADDING };

    // DC de medição
    HDC hdc = GetDC(hwnd);

    // Região do texto (engrossada)
    FreeRgn(G.textRgn);
    G.textRgn = BuildTextRegion(hdc, G.badge);

    // Bounding box do texto
    RECT tb; GetRgnBox(G.textRgn, &tb);

    // Grid (com seu ajuste "+9" no cell_h)
    double cellW = (double)(tb.right - tb.left) / COLS;
    double cellH = (double)(tb.bottom - tb.top) / ROWS + 9.0;  // <<< ajuste pedido
    double cell  = std::max(0.5, std::min(cellW, cellH));
    int    block = (int)std::max(1.0, cell - BLOCK_GAP);

    double originX = tb.left + ((tb.right - tb.left) - COLS * cell) / 2.0;
    double originY = tb.top  + ((tb.bottom - tb.top) - ROWS * cell) / 2.0;

    // Monta células válidas, já na ordem esq→dir e baixo→cima
    G.cells.clear();
    for (int c = 0; c < COLS; ++c) {
        for (int r = ROWS - 1; r >= 0; --r) { // bottom->top
            int x = (int)std::round(originX + c * cell + (cell - block) / 2.0);
            int y = (int)std::round(originY + r * cell + (cell - block) / 2.0);
            RECT cellRc = { x, y, x + block, y + block };
            if (RectInRegion(G.textRgn, &cellRc)) {
                G.cells.push_back({ cellRc });
            }
        }
    }

    // Timeline baseada somente nos blocos válidos
    G.totalBlocks = (int)G.cells.size();
    if (G.totalBlocks <= 0) G.totalBlocks = 1;
    G.buildTime = G.totalBlocks * STEP_MS;
    G.cycleMs   = G.buildTime + HOLD_MS + G.buildTime;
    G.elapsedMs = 0;

    ReleaseDC(hwnd, hdc);
}

// Quantos blocos devem estar ativos nesse instante?
static int ActiveCount() {
    int t = G.elapsedMs;
    if (t < G.buildTime) {
        return (t / STEP_MS) + 1;
    }
    t -= G.buildTime;
    if (t < HOLD_MS) {
        return G.totalBlocks;
    }
    t -= HOLD_MS;
    int off = (t / STEP_MS) + 1;
    int res = G.totalBlocks - off;
    return (res < 0) ? 0 : res;
}

// Desenha gradiente de fundo na DC (msimg32::GradientFill)
static void PaintGradient(HDC hdc, RECT rc) {
    TRIVERTEX vtx[2];
    GRADIENT_RECT gr = {0,1};
    vtx[0].x = rc.left;  vtx[0].y = rc.top;
    vtx[1].x = rc.right; vtx[1].y = rc.bottom;
    auto c0 = BG_TOP;    auto c1 = BG_BOTTOM;
    vtx[0].Red   = GetRValue(c0) << 8; vtx[0].Green = GetGValue(c0) << 8; vtx[0].Blue  = GetBValue(c0) << 8; vtx[0].Alpha = 0;
    vtx[1].Red   = GetRValue(c1) << 8; vtx[1].Green = GetGValue(c1) << 8; vtx[1].Blue  = GetBValue(c1) << 8; vtx[1].Alpha = 0;
    GradientFill(hdc, vtx, 2, &gr, 1, GRADIENT_FILL_RECT_V);
}

// Desenha uma borda rounded
static void DrawBadge(HDC hdc, const RECT& r, double breathPhase) {
    // “respiração”: 1.2% de scale no retângulo
    double s = 1.0 + 0.012 * std::sin(2.0 * 3.141592653589793 * breathPhase);
    int w = r.right - r.left;
    int h = r.bottom - r.top;
    int nx = (int)(w * (1.0 - s) / 2.0);
    int ny = (int)(h * (1.0 - s) / 2.0);
    RECT rr = { r.left - nx, r.top - ny, r.right + nx, r.bottom + ny };

    HPEN pen = CreatePen(PS_SOLID, 6, BORDER);
    HGDIOBJ oldP = SelectObject(hdc, pen);
    HGDIOBJ oldB = SelectObject(hdc, GetStockObject(NULL_BRUSH));

    RoundRect(hdc, rr.left, rr.top, rr.right, rr.bottom, BADGE_RX, BADGE_RX);

    SelectObject(hdc, oldB);
    SelectObject(hdc, oldP);
    DeleteObject(pen);
}

// Pintura com double-buffering
static void Paint(HWND hwnd) {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);
    RECT rc; GetClientRect(hwnd, &rc);

    // backbuffer
    HDC memdc = CreateCompatibleDC(hdc);
    HBITMAP membmp = CreateCompatibleBitmap(hdc, rc.right-rc.left, rc.bottom-rc.top);
    HGDIOBJ oldbmp = SelectObject(memdc, membmp);

    // BG
    PaintGradient(memdc, rc);

    // Badge + blocos
    double breathPhase = (double)(G.elapsedMs % BREATH_MS) / (double)BREATH_MS;
    DrawBadge(memdc, G.badge, breathPhase);

    // Clipa no texto (opcional, os blocos já são válidos)
    SelectClipRgn(memdc, G.textRgn);

    // Blocos ativos
    int active = ActiveCount();
    if (active > (int)G.cells.size()) active = (int)G.cells.size();
    HBRUSH b = CreateSolidBrush(BLOCK_COL);
    HGDIOBJ oldB = SelectObject(memdc, b);
    HPEN oldPen = (HPEN)SelectObject(memdc, GetStockObject(NULL_PEN));
    for (int i = 0; i < active; ++i) {
        const RECT& r = G.cells[i].rc;
        Rectangle(memdc, r.left, r.top, r.right, r.bottom);
    }
    SelectObject(memdc, oldPen);
    SelectObject(memdc, oldB);
    DeleteObject(b);

    // remove clip
    SelectClipRgn(memdc, NULL);

    // “sombra” simples do texto (preenchimento sólido escuro)
    HBRUSH sh = CreateSolidBrush(RGB(0,0,0));
    FrameRgn(memdc, G.textRgn, sh, 1, 1); // discreto
    DeleteObject(sh);

    // blit
    BitBlt(hdc, 0, 0, rc.right, rc.bottom, memdc, 0, 0, SRCCOPY);

    // cleanup
    SelectObject(memdc, oldbmp);
    DeleteObject(membmp);
    DeleteDC(memdc);

    EndPaint(hwnd, &ps);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE:
        SetTimer(hwnd, 1, 16, NULL); // ~60 fps
        return 0;
    case WM_SIZE:
        RebuildLayout(hwnd);
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    case WM_TIMER:
        if (wParam == 1) {
            // timeline
            G.elapsedMs = (G.elapsedMs + 16) % (G.cycleMs ? G.cycleMs : 1);
            InvalidateRect(hwnd, NULL, FALSE);
        }
        return 0;
    case WM_KEYDOWN:
        if (wParam == VK_ESCAPE) DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        KillTimer(hwnd, 1);
        FreeRgn(G.textRgn);
        PostQuitMessage(0);
        return 0;
    case WM_PAINT:
        Paint(hwnd);
        return 0;
    default:
        return DefWindowProc(hwnd, msg, wParam, lParam);
    }
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int nCmd) {
    // Janela básica
    const wchar_t* cls = L"ItauLoaderWin32";
    WNDCLASSW wc = {};
    wc.hInstance = hInst;
    wc.lpszClassName = cls;
    wc.lpfnWndProc = WndProc;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    RegisterClassW(&wc);

    // Fullscreen borderless (pode trocar para janela normal)
    RECT desk; GetWindowRect(GetDesktopWindow(), &desk);
    HWND hwnd = CreateWindowExW(
        WS_EX_TOPMOST, cls, L"Itaú Loader (Win32/GDI)",
        WS_POPUP, desk.left, desk.top, desk.right, desk.bottom,
        NULL, NULL, hInst, NULL
    );
    ShowWindow(hwnd, nCmd ? nCmd : SW_SHOW);
    UpdateWindow(hwnd);

    // Primeira construção do layout
    RebuildLayout(hwnd);

    // Loop
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return (int)msg.wParam;
}

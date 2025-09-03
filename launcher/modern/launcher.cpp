/*------------------------------------------------------------------------------
  LAUNCHER C++ — Win32 + GDI+ (single-file, neon futurista)
  (versão: janela borderless fixa + timeout 60s + strings em UTF-8)
  (update: bordas escaláveis via kBorderScale + spinner em #FF4081 / #7C4DFF)

  ✔ Um único arquivo .cpp (sem .h, sem assets externos)
  ✔ Janela BORDERLESS (WS_POPUP), sem botões de minimizar/maximizar/fechar
  ✔ Posicionada no monitor onde está o mouse (tamanho padrão 1100x700)
  ✔ Fecha automaticamente após 60 segundos (timeout de inicialização)
  ✔ Shading radial (centro → bordas) com PathGradientBrush (vinheta)
  ✔ 3 modos de loading (Orbital, Barra de energia, Triângulo pulsante)
  ✔ Frases “estilo The Sims” (fade/balanço/auto-rotate + F1)
  ✔ Microinterações: toast, hover-boost, tema claro/escuro
  ✔ High-DPI aware (Per-Monitor v2), double buffering
  ✔ Screenshot PNG (Ctrl+S)
  ✔ Persistência simples de tema/modo (HKCU\Software\NeonLauncher)

  ---------------------------------------------------------------------------
  COMO COMPILAR (UTF-8)
  ---------------------------------------------------------------------------

  MSVC (x64 ou x86):
    cl /std:c++20 /utf-8 /W4 /EHsc /DUNICODE /D_UNICODE launcher.cpp ^
       /link Gdiplus.lib User32.lib Gdi32.lib UxTheme.lib Dwmapi.lib Shlwapi.lib Advapi32.lib

  MinGW-w64 (x86_64):
    g++ -std=c++20 -municode -O2 -Wall -Wextra -Wno-unknown-pragmas launcher.cpp -o launcher.exe \
        -lgdiplus -luser32 -lgdi32 -luxtheme -ldwmapi -lshlwapi -ladvapi32

  Observações:
  - Salve este arquivo como UTF-8 (idealmente com BOM). /utf-8 ajuda o MSVC a ler acentuação.
------------------------------------------------------------------------------*/

#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0A00 // Windows 10
#pragma execution_character_set("utf-8") // MSVC: interpreta literais como UTF-8

#include <windows.h>
#include <windowsx.h>          // GET_X_LPARAM / GET_Y_LPARAM
#include <objidl.h>            // IStream, IUnknown — deve vir ANTES de Gdiplus.h
#include <gdiplus.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <shlwapi.h>
#include <shellapi.h>

#include <string>
#include <vector>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cassert>

#pragma comment(lib, "Gdiplus.lib")
#pragma comment(lib, "Dwmapi.lib")
#pragma comment(lib, "Shlwapi.lib")
#pragma comment(lib, "UxTheme.lib")
#pragma comment(lib, "User32.lib")
#pragma comment(lib, "Gdi32.lib")
#pragma comment(lib, "Advapi32.lib")

using namespace Gdiplus;

// ===== 1) INCLUDES & UTILITÁRIOS ===================================================

using fSetProcessDpiAwarenessContext = BOOL (WINAPI*)(HANDLE);

static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float lerpf(float a, float b, float t) { return a + (b - a) * t; }
static inline BYTE  mulAlpha(BYTE a, float k){
    const float v = (float)a * clampf(k, 0.f, 1.f);
    int iv = (int)std::lround(v);
    if (iv < 0) iv = 0; else if (iv > 255) iv = 255;
    return (BYTE)iv;
}

// Easing helpers
static inline float easeInOutQuart(float t){
    t = clampf(t, 0.f, 1.f);
    return t < 0.5f ? 8.f*t*t*t*t : 1.f - std::pow(-2.f*t + 2.f, 4.f)/2.f;
}
static inline float easeOutCubic(float t){
    t = clampf(t, 0.f, 1.f);
    return 1.f - std::pow(1.f - t, 3.f);
}

// Ruído simples determinístico
static inline float fhash(float x){
    float s = sinf(x*12.9898f) * 43758.5453f;
    return s - floorf(s);
}

// QPC timer
struct HiTimer {
    LARGE_INTEGER freq{}, last{};
    double dt = 0.0, smoothedFps = 60.0;
    void init(){
        QueryPerformanceFrequency(&freq);
        QueryPerformanceCounter(&last);
    }
    void tick(){
        LARGE_INTEGER now; QueryPerformanceCounter(&now);
        dt = double(now.QuadPart - last.QuadPart) / double(freq.QuadPart);
        last = now;
        const double fps = (dt > 0.000001) ? 1.0/dt : 999.0;
        smoothedFps = smoothedFps*0.9 + fps*0.1;
    }
};

// RAII para GDI+
struct GdiPlusRAII {
    ULONG_PTR token{};
    bool ok = false;
    GdiPlusRAII(){
        GdiplusStartupInput si;
        ok = (GdiplusStartup(&token, &si, nullptr) == Ok);
    }
    ~GdiPlusRAII(){ if(ok) GdiplusShutdown(token); }
};

// ===== 2) CONFIG ===================================================================

static const wchar_t* kRegPath = L"Software\\NeonLauncher";
static const int   kBaseDPI = 96;
static const float kPhraseMinSec = 2.0f;
static const float kPhraseMaxSec = 5.0f;
static const float kModeFadeSec  = 0.32f;     // 250–400 ms
static const float kToastSec     = 1.0f;      // fade total 1s
static const float kPhraseFadeSec= 0.35f;
static const float kHudFontPt    = 11.f;
static const UINT  kTimerFrameId = 1;
static const UINT  kTimerExitId  = 2;          // timeout 60s
static const UINT  kTimerProbeId = 3;       // timer para sondar sinal da app
static const UINT  kTimerLaunchDelayId = 4;
static const UINT  kExitTimeoutMs= 60000;
static const UINT  kProbeIntervalMs  = 200;     // sonda a cada 200ms
static const UINT  kLaunchDelayMs= 10000;      // delay antes de lançar a app

// === App principal a ser lançada ===
static const wchar_t* kAppToRun  = L"chatbotai.exe"; // ajuste se o nome for diferente
static const wchar_t* kAppArgs   = L"";              // ex.: L"--profile=default"

// Handle do processo da app (usado para fallback opcional)
static HANDLE gChildProc = nullptr;

// ===== SINAL DE PRONTO (ready) VIA EVENTO GLOBAL ==================================
// Nomes possíveis do evento (ajuste se sua app usar outro)
static const wchar_t* kReadyEventNames[] = {
    L"Local\\CHATBOT_AI_READY",
    L"Global\\CHATBOT_AI_READY",
    L"CHATBOT_AI_READY",
};

static HANDLE gReadyEvent = nullptr;

static HANDLE EnsureReadyEvent(){
    for (auto name : kReadyEventNames){
        HANDLE h = CreateEventW(nullptr, TRUE, FALSE, name);
        if (h) return h;
    }
    return nullptr;
}

static bool CheckReadySignal(){
    if (!gReadyEvent){
        gReadyEvent = EnsureReadyEvent();
        return false;
    }
    return WaitForSingleObject(gReadyEvent, 0) == WAIT_OBJECT_0;
}

// Lança a app principal ao lado do launcher e guarda o handle do processo.
static void LaunchMainApp()
{
    wchar_t moduleDir[MAX_PATH];
    if (GetModuleFileNameW(nullptr, moduleDir, MAX_PATH) == 0) return;
    PathRemoveFileSpecW(moduleDir); // pasta do launcher

    // caminho completo para a app
    wchar_t appPath[MAX_PATH];
    lstrcpyW(appPath, moduleDir);
    PathAppendW(appPath, kAppToRun);

    if (!PathFileExistsW(appPath)) {
        // sem app => apenas deixa o splash/timeout existir
        return;
    }

    SHELLEXECUTEINFOW sei{};
    sei.cbSize       = sizeof(sei);
    sei.fMask        = SEE_MASK_NOCLOSEPROCESS;
    sei.lpVerb       = L"open";
    sei.lpFile       = appPath;
    sei.lpParameters = (kAppArgs && kAppArgs[0]) ? kAppArgs : nullptr;
    sei.lpDirectory  = moduleDir;               // working dir correto (Qt/plugins/relativos)
    sei.nShow        = SW_SHOWNORMAL;

    if (ShellExecuteExW(&sei)) {
        if (sei.hProcess) gChildProc = sei.hProcess;
    }
}

// ======== CONTROLE ÚNICO DE BORDAS (knob) =========================================
// Aumente/diminua este valor para engrossar/afinar TODAS as bordas visuais do frame.
static const float kBorderScale  = 2.0f;   // <<<<<< ajuste aqui (ex.: 1.0, 1.5, 2.0)
static const int   kFrameLayers  = 3;      // número de camadas de borda do perímetro

// Paletas (tema do fundo/texto/bubbles)
struct Theme {
    Color bg;          // fundo base
    Color vignette;    // borda vinheta (opaca)
    Color c1, c2, c3;  // acentos (mantidos para UI, não para spinner)
    Color text;        // texto
    Color textShadow;  // sombra do texto
    Color bubble;      // caixa frase
    Color bubbleGlow;  // glow leve
};
static Theme DarkTheme {
    Color(0xFF, 0x0B,0x0F,0x1A),         // bg #0B0F1A
    Color(0xCC, 0x00,0x00,0x00),         // vinheta (alpha ~0.8)
    Color(0xFF, 0x21,0xD4,0xFD),         // acentos gerais UI (não spinner)
    Color(0xFF, 0xB7,0x21,0xFF),
    Color(0xFF, 0x6C,0x2B,0xD9),
    Color(0xFF, 0xF9,0xFA,0xFB),         // texto
    Color(0x66, 0x00,0x00,0x00),         // sombra 30~40%
    Color(0xCC, 0x18,0x1E,0x2A),         // bubble escura
    Color(0x55, 0xB7,0x21,0xFF),         // glow da bubble
};
static Theme LightTheme {
    Color(0xFF, 0xF6,0xF7,0xFB),         // bg claro
    Color(0x99, 0x00,0x00,0x00),         // vinheta
    Color(0xFF, 0x21,0xB4,0xFD),
    Color(0xFF, 0xA1,0x31,0xFF),
    Color(0xFF, 0x70,0x3B,0xD9),
    Color(0xFF, 0x12,0x14,0x18),         // texto escuro
    Color(0x55, 0x00,0x00,0x00),
    Color(0xCC, 0xFF,0xFF,0xFF),         // bubble clara
    Color(0x33, 0x21,0xB4,0xFD),
};

// ======== CORES DO SPINNER =========================================================
// Baseadas nas pedidas: #FF4081 (rosa) e #7C4DFF (roxo)
static const Color kSpinA(0xFF, 0xFF, 0x40, 0x81); // #FF4081
static const Color kSpinB(0xFF, 0x7C, 0x4D, 0xFF); // #7C4DFF

static inline Color LerpColor(const Color& a, const Color& b, float t){
    t = clampf(t, 0.f, 1.f);
    BYTE A = (BYTE)std::lround(lerpf((float)a.GetA(), (float)b.GetA(), t));
    BYTE R = (BYTE)std::lround(lerpf((float)a.GetR(), (float)b.GetR(), t));
    BYTE G = (BYTE)std::lround(lerpf((float)a.GetG(), (float)b.GetG(), t));
    BYTE B = (BYTE)std::lround(lerpf((float)a.GetB(), (float)b.GetB(), t));
    return Color(A,R,G,B);
}
static inline Color WithAlpha(const Color& c, float a){ return Color(mulAlpha(c.GetA(), a), c.GetR(), c.GetG(), c.GetB()); }

// ===== 3) ESTADO GLOBAL ============================================================

enum class Mode : int { Orbital=0, Energy=1, Triangle=2 };

struct AppState {
    HWND   hwnd{};
    HINSTANCE hinst{};
    GdiPlusRAII gdi;
    bool   gdiOk = false;

    // janela & dpi
    int    dpi = kBaseDPI;
    float  scale = 1.f;
    int    cw = 1100, ch = 700;

    // tema/modo
    int    themeIndex = 1; // 0 dark, 1 light
    Mode   mode = Mode::Orbital;
    Mode   nextMode = Mode::Orbital;
    bool   switching = false;
    float  switchT = 0.f;

    // animação
    HiTimer timer;
    bool   paused = false;
    double t = 0.0;          // tempo total

    // frases
    std::vector<std::wstring> phrases;
    int    phraseIndex = 0;
    float  phraseAlpha = 1.f;
    float  phraseTimer = 0.f;
    float  phraseInterval = 4.f;
    bool   phraseFadingOut = false;

    // toast
    std::wstring toast;
    float  toastTimer = 0.f; // [0..kToastSec]

    // hover
    bool   hoverBoost = false;

    // hud
    bool   showHud = false;

    // persistência
    void loadPersist(){
        HKEY k{};
        if (RegCreateKeyExW(HKEY_CURRENT_USER, kRegPath, 0, nullptr, 0, KEY_READ|KEY_WRITE, nullptr, &k, nullptr) == ERROR_SUCCESS){
            DWORD v=0, sz=sizeof(v);
            if (RegQueryValueExW(k, L"Theme", nullptr, nullptr, reinterpret_cast<LPBYTE>(&v), &sz) == ERROR_SUCCESS)
                themeIndex = (v?1:0);
            if (RegQueryValueExW(k, L"Mode", nullptr, nullptr, reinterpret_cast<LPBYTE>(&v), &sz) == ERROR_SUCCESS)
                mode = (Mode)(v%3);
            RegCloseKey(k);
        }
    }
    void savePersist(){
        HKEY k{};
        if (RegCreateKeyExW(HKEY_CURRENT_USER, kRegPath, 0, nullptr, 0, KEY_READ|KEY_WRITE, nullptr, &k, nullptr) == ERROR_SUCCESS){
            DWORD v = (DWORD)themeIndex; RegSetValueExW(k, L"Theme", 0, REG_DWORD, (BYTE*)&v, sizeof(v));
            v = (DWORD)mode;             RegSetValueExW(k, L"Mode",  0, REG_DWORD, (BYTE*)&v, sizeof(v));
            RegCloseKey(k);
        }
    }
} g;

// ===== 4) FRASES “THE SIMS” (ASCII-safe) ==========================================
static std::vector<std::wstring> make_phrases(){
    return {
        L"Se der ruim, a culpa e do gato no teclado",
        L"Instalando shaders quanticos (mentira... ou nao?)",
        L"O futuro chegou; so falta carregar",
        L"Seu PC esta 63% mais lindo agora",
        L"Teleportando assets inexistentes... uau!",
        L"Fazendo carinho na GPU",
        L"Preparando o modo foco: shhh",
        L"Renderizando aquele 'uhul'",
        L"Quase la... tipo, quase quase",
        L"Respira... inspira... anima!",
        L"Pausa dramatica para suspense",
        L"Se for bug, vira feature com glow",
        L"Colando glitter no algoritmo",
        L"Aquecendo o laranja Itaú no modo neon",
        L"StackSpot AI abrindo a mente e fechando bugs",
        L"Cafezinho coado em JIT, produtividade em ascensao",
        L"Sincronizando contextos e desincronizando o sono",
        L"Compilando ideias, linkando coragem",
        L"BRB: alinhando deploy com a Lua nova",
        L"Carregando plugins do Qt sem drama hoje",
        L"Bendita seja a pipeline que passa de primeira",
        L"Preparando a retrô com pão de queijo estrategico",
        L"Fazendo carinho no Kafka para as mensagens fluirem",
        L"Coletando logs e devolvendo paz",
        L"Chamando o SRE espiritual para benzer o deploy",
        L"StackSpot AI carregando memórias do projeto",
        L"Destravando PRs com diplomacia e cafe",
        L"Agro e tech: adubando commits",
        L"Custodia de bugs sob guarda reforcada",
        L"Criptografando desculpas para a retro",
        L"Detectando feature que nasceu bug mas tem futuro",
        L"Renderizando aquele brilho no olho corporativo",
        L"Alocando energia extra para a hora extra",
        L"Refatorando a segunda-feira em coisa boa",
        L"Desfragmentando backlog e juntando coragem",
        L"Varrendo a fila do SQS com vassoura mágica",
        L"Carregando dashboards para provar que funciona",
        L"Fazendo pair programming com o destino",
        L"Preparando rollback so por supersticao",
        L"Blindando tokens contra azar de sexta-feira",
        L"Redimensionando ambicao para caber no sprint",
        L"Evangelizando o linter com bons modos",
        L"Cacheando cafe para uso intensivo",
        L"Chamando a deidade dos drivers de video",
        L"Orquestrando threads para dancar em harmonia",
        L"Elevando o cold start ao estado zen",
        L"Semeando testes e colhendo confianca",
        L"Polindo bordas ate refletirem boas praticas",
        L"Gerando instalador que TI corporativa chama de lindo",
        L"Pedindo benção ao compliance e seguindo viagem",
        L"Somando cafe com foco e dividindo ansiedade",
        L"Negociando prazo com o destino: aprovado",
        L"Guardando segredos no .env e no coracao",
        L"Roteando notificacoes direto para a alegria",
        L"Fazendo merge sem deixar marcas",
        L"Pre-aquecendo o cérebro para o code review",
        L"Debugando pensamento ate virar plano",
        L"Prendendo o caos no try/catch",
        L"Verificando certificados e energias",
        L"Dando foco ao foco com foco",
        L"Curvando o tempo para caber mais uma tarefa",
        L"Promovendo a paz mundial entre threads",
        L"Convencendo a GPU a participar da festa",
        L"Chamando o modo ninja: silencioso e eficiente",
        L"Lapidando telemetria para so brilhar o que importa",
        L"Guardando um rollback debaixo do travesseiro",
        L"Ensinando o app a gostar de segunda",
        L"Fechando o escopo e abrindo um sorriso",
        L"Atualizando drivers de esperança",
        L"Transformando overtime em overtudo",
        L"Elevando a UX ao estado de arte silenciosa"
    };
}

// ===== Helpers de DPI & cores ======================================================
static inline int Dp(float px){ return (int)std::lround(px * g.scale); }
static inline Color alpha(const Color& c, float a){
    return Color(mulAlpha(c.GetA(), a), c.GetR(), c.GetG(), c.GetB());
}

// ===== 5) FUNÇÕES DE DESENHO =======================================================

// --- Rounded rect helpers
static void AddRoundRect(GraphicsPath& p, const Rect& r, int rad){
    const int d = rad*2;
    p.AddArc(r.X, r.Y, d, d, 180.0f, 90.0f);
    p.AddArc(r.X + r.Width - d, r.Y, d, d, 270.0f, 90.0f);
    p.AddArc(r.X + r.Width - d, r.Y + r.Height - d, d, d,   0.0f, 90.0f);
    p.AddArc(r.X, r.Y + r.Height - d, d, d,  90.0f, 90.0f);
    p.CloseFigure();
}
static void FillRoundedRectangle(Graphics* gfx, Brush* b, const Rect& r, int rad){
    GraphicsPath p; AddRoundRect(p, r, rad); gfx->FillPath(b, &p);
}
static void DrawRoundedRectangle(Graphics* gfx, Pen* pen, const Rect& r, int rad){
    GraphicsPath p; AddRoundRect(p, r, rad); gfx->DrawPath(pen, &p);
}

static Theme& CurTheme(){ return (g.themeIndex==0)? DarkTheme : LightTheme; }

// Moldura com várias camadas — controlada por kBorderScale
static void DrawFrameBorders(Graphics& gfx){
    gfx.SetSmoothingMode(SmoothingModeHighQuality);

    // base de espessuras derivadas do knob
    const float baseStroke = (float)Dp(1.6f) * kBorderScale;
    const int   insetStep  = Dp(8.0f);          // distância entre camadas
    Rect rc(Dp(14.0f), Dp(12.0f), g.cw - Dp(28.0f), g.ch - Dp(24.0f));

    for (int i=0; i<kFrameLayers; ++i){
        const float t = (float)i / std::max(1, kFrameLayers-1);
        // cor intercalando entre as bases do spinner (rosa/roxo) para “costurar” a UI
        Color c = LerpColor(kSpinA, kSpinB, t);
        Pen pen(WithAlpha(c, 0.35f * (1.0f - 0.15f*(float)i)), (REAL)(baseStroke + i*0.5f));
        pen.SetLineJoin(LineJoinRound); pen.SetStartCap(LineCapRound); pen.SetEndCap(LineCapRound);
        const int rad = std::max(Dp(16) - i*Dp(3), Dp(6));
        DrawRoundedRectangle(&gfx, &pen, rc, rad);

        // shrink para a próxima camada
        rc.X += insetStep; rc.Y += insetStep;
        rc.Width  -= insetStep*2; rc.Height -= insetStep*2;
        if (rc.Width <= 0 || rc.Height <= 0) break;
    }
}

static void DrawBackgroundRadialVignette(Graphics& gfx){
    const Theme& th = CurTheme();
    gfx.Clear(th.bg);

    // Vinheta radial centro transparente → bordas opacas
    GraphicsPath path; path.AddRectangle(Rect(0,0,g.cw,g.ch));
    PathGradientBrush pgb(&path);
    const PointF center((REAL)g.cw*0.5f, (REAL)g.ch*0.5f);
    pgb.SetCenterPoint(center);
    const Color centerC = alpha(th.bg, 0.05f);
    pgb.SetCenterColor(centerC);
    Color surrounds[] = { alpha(th.vignette, 1.0f) };
    INT cnt = 1; pgb.SetSurroundColors(surrounds, &cnt);
    gfx.FillRectangle(&pgb, 0,0,g.cw,g.ch);

    // Ruído sutil
    const int step = Dp(8.0f);
    SolidBrush dot(alpha(th.text, 0.06f));
    for (int y=0; y<g.ch; y+=step){
        for (int x=0; x<g.cw; x+=step){
            const float r = fhash((float)x*0.173f + (float)y*0.7f);
            if (r > 0.88f) gfx.FillRectangle(&dot, x, y, 1, 1);
        }
    }
}

static void DrawNeonGlowOverlay(Graphics& gfx){
    // Camadas de borda do perímetro (controladas por kBorderScale)
    DrawFrameBorders(gfx);

    // Alguns detalhes de linhas/arcos leves por cima
    gfx.SetSmoothingMode(SmoothingModeHighQuality);

    Pen glow(WithAlpha(kSpinB, 0.12f), (REAL)(Dp(1.8f) * kBorderScale));
    glow.SetLineJoin(LineJoinRound); glow.SetStartCap(LineCapRound); glow.SetEndCap(LineCapRound);

    const RectF rf((REAL)Dp(18), (REAL)Dp(16), (REAL)(g.cw - Dp(36)), (REAL)(g.ch - Dp(32)));
    gfx.DrawArc(&glow, rf, 10.0f, 80.0f);
    gfx.DrawArc(&glow, rf, 200.0f, 60.0f);

    Pen line(WithAlpha(kSpinA, 0.10f), (REAL)(Dp(1.0f) * kBorderScale));
    line.SetLineJoin(LineJoinRound); line.SetStartCap(LineCapRound); line.SetEndCap(LineCapRound);
    gfx.DrawLine(&line, (REAL)Dp(30), (REAL)Dp(60), (REAL)(g.cw - Dp(60)), (REAL)Dp(30));
    gfx.DrawLine(&line, (REAL)Dp(40), (REAL)(g.ch - Dp(50)), (REAL)(g.cw - Dp(30)), (REAL)(g.ch - Dp(20)));
}

// ————— Loading Mode 1: Orbital (usa kSpinA/kSpinB)
static void DrawLoading_Orbital(Graphics& gfx, float globalAlpha, float t, float cx, float cy){
    gfx.SetSmoothingMode(SmoothingModeHighQuality);

    const int rings = 3;
    const int perRing = 8;
    for (int r=0; r<rings; ++r){
        const float baseR = (float)Dp(70.0f + r*32.0f);
        const float puls = 1.0f + 0.07f * sinf(t*2.2f + (float)r);
        const float R = baseR * puls;
        for (int i=0;i<perRing;++i){
            const float w = (float)i/(float)perRing;
            const float ang = t*(1.3f + 0.25f*(float)r) + w*6.28318f;
            // trail: ghosts
            for (int k=4; k>=0; --k){
                const float dt = 0.022f*(float)k;
                const float a  = globalAlpha * (0.18f + 0.16f*(float)(4-k));
                const float rr = R * (1.f - 0.03f*(float)k);
                const float x = cx + rr * cosf(ang - dt*4.5f);
                const float y = cy + rr * sinf(ang - dt*4.5f);
                const float sz = (float)Dp(6.f + 2.f*(r==0 ? 1.f:0.f) + 1.5f*(k==0 ? 1.f:0.f));

                // variação suave entre as duas cores
                const float mix = 0.5f + 0.5f*sinf(t*0.9f + w*6.28318f + r);
                Color cc = LerpColor(kSpinA, kSpinB, mix);
                SolidBrush b( WithAlpha(cc, a) );
                gfx.FillEllipse(&b, (REAL)(x - sz*0.5f), (REAL)(y - sz*0.5f), (REAL)sz, (REAL)sz);
            }
        }
    }
    // círculo central sutil (roxo/rosa mix)
    const float pulse = 0.25f + 0.75f * fabsf(sinf(t*1.4f));
    Color edge = LerpColor(kSpinB, kSpinA, pulse*0.5f);
    Pen p(WithAlpha(edge, globalAlpha*0.35f), (REAL)Dp(2) * kBorderScale);
    p.SetLineJoin(LineJoinRound); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    gfx.DrawEllipse(&p, (REAL)(cx - (float)Dp(30)), (REAL)(cy - (float)Dp(30)), (REAL)Dp(60), (REAL)Dp(60));
}

// ————— Loading Mode 2: Barra de energia (gradiente entre kSpinA/kSpinB)
static void DrawLoading_Energy(Graphics& gfx, float globalAlpha, float t, float cx, float cy){
    gfx.SetSmoothingMode(SmoothingModeHighQuality);

    const int W = Dp(420), H = Dp(38);
    const RectF box((REAL)(cx - W/2.0f), (REAL)(cy - H/2.0f), (REAL)W, (REAL)H);

    // fundo + borda
    const float stroke = (float)Dp(1.5f) * kBorderScale;
    SolidBrush bb(alpha(CurTheme().bubble, globalAlpha*0.85f));
    Pen       bo(WithAlpha(kSpinB, globalAlpha*0.6f), (REAL)stroke);
    bo.SetLineJoin(LineJoinRound); bo.SetStartCap(LineCapRound); bo.SetEndCap(LineCapRound);
    gfx.FillRectangle(&bb, box);
    gfx.DrawRectangle(&bo, box);

    // picos (colunas) com noise — cores variam de kSpinA a kSpinB
    const int cols = 64;
    const float colW = (float)W / (float)cols;
    for (int i=0;i<cols;++i){
        const float u = (float)i/(float)(cols-1);
        const float n = 0.55f + 0.45f * (0.6f*sinf(t*1.9f + u*6.3f) + 0.4f*sinf(t*3.3f + u*13.0f + 1.234f));
        const float h = (float)(H - Dp(8)) * (0.15f + 0.85f*n);
        RectF r((REAL)(box.X + (float)i*colW + 1.f), (REAL)(box.Y + box.Height - h - (float)Dp(3)),
                (REAL)(colW - 2.f), (REAL)h);

        const float mix = 0.35f + 0.65f * n;
        Color cTop = LerpColor(kSpinA, kSpinB, mix);
        Color cBot = LerpColor(kSpinA, kSpinB, mix*0.6f);

        SolidBrush bBot(WithAlpha(cBot, globalAlpha*(0.28f+0.30f*n)));
        SolidBrush bTop(WithAlpha(cTop, globalAlpha*(0.40f+0.35f*n)));
        gfx.FillRectangle(&bBot, r);
        r.Y += (REAL)Dp(4); r.Height -= (REAL)Dp(4);
        gfx.FillRectangle(&bTop, r);
    }

    // highlight especular
    Pen hi(Color(255,255,255,255), (REAL)(Dp(1.0f) * kBorderScale));
    hi.SetColor(alpha(Color(255,255,255,255), globalAlpha*0.35f));
    gfx.DrawLine(&hi, box.X + (REAL)Dp(6), box.Y + (REAL)Dp(8),
                      box.X + box.Width - (REAL)Dp(6), box.Y + (REAL)Dp(8));
}

// ————— Loading Mode 3: Triângulo pulsante (contorno pulsa entre as cores)
static void DrawLoading_Triangle(Graphics& gfx, float globalAlpha, float t, float cx, float cy){
    gfx.SetSmoothingMode(SmoothingModeHighQuality);

    const float S = (float)Dp(160.0f);
    PointF A((REAL)cx, (REAL)(cy - S*0.8f)), B((REAL)(cx - S*0.9f), (REAL)(cy + S*0.7f)), C((REAL)(cx + S*0.9f), (REAL)(cy + S*0.7f));

    // rotação ~15°
    const float ang = 15.0f * 3.1415926f / 180.0f;
    auto rot = [&](PointF p)->PointF{
        const float x = p.X - (REAL)cx, y = p.Y - (REAL)cy;
        const float xr =  cosf(ang)*x - sinf(ang)*y;
        const float yr =  sinf(ang)*x + cosf(ang)*y;
        return PointF((REAL)(cx + xr), (REAL)(cy + yr));
    };
    A = rot(A); B = rot(B); C = rot(C);

    GraphicsPath tri; std::array<PointF,3> arr{A,B,C}; tri.AddPolygon(arr.data(), 3);

    // contorno com “pulsos” coloridos
    const float pulse = 0.25f + 0.75f * fabsf(sinf(t*1.7f));
    Color edge = LerpColor(kSpinB, kSpinA, pulse);
    Pen  outline(WithAlpha(edge, globalAlpha*(0.35f + 0.45f*pulse)), (REAL)(Dp(3.0f) * kBorderScale));
    outline.SetLineJoin(LineJoinRound); outline.SetStartCap(LineCapRound); outline.SetEndCap(LineCapRound);
    gfx.DrawPath(&outline, &tri);

    // barras internas varrendo (clipping ao triângulo) — rosa dominante
    Region clip(&tri); gfx.SetClip(&clip, CombineModeReplace);
    for (int i=0;i<3;++i){
        const float k = fmodf(t*(0.6f+(float)i*0.12f), 1.0f);
        const float yy = lerpf(B.Y, A.Y, k);
        Color barC = LerpColor(kSpinA, kSpinB, 0.25f + 0.25f*(float)i);
        SolidBrush bA(WithAlpha(barC, globalAlpha*(0.18f + 0.15f*(float)i)));
        gfx.FillRectangle(&bA, (REAL)(B.X + (float)Dp(8)), (REAL)(yy - (float)Dp(4)),
                               (REAL)(C.X - B.X - (float)Dp(16)), (REAL)Dp(8));
    }
    gfx.ResetClip();
}

// ————— Frase (bubble) ============================================================
static void DrawPhraseBubble(Graphics& gfx, std::wstring_view text, float alpha01){
    if (alpha01 <= 0.f) return;
    const Theme& th = CurTheme();
    gfx.SetSmoothingMode(SmoothingModeHighQuality);
    gfx.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);

    const int padX = Dp(18.0f), padY = Dp(12.0f);
    const int maxW = std::min(g.cw - Dp(120.0f), Dp(820.0f));

    FontFamily ff(L"Segoe UI");
    Font title(&ff, (REAL)Dp(20.0f), FontStyleBold, UnitPixel);
    StringFormat fmt; fmt.SetAlignment(StringAlignmentCenter); fmt.SetLineAlignment(StringAlignmentNear);
    RectF layout((REAL)((g.cw - maxW)/2), (REAL)Dp(28.0f), (REAL)maxW, (REAL)Dp(200.0f));
    RectF bounds{}; gfx.MeasureString(text.data(), (INT)text.size(), &title, layout, &fmt, &bounds);

    const float wob = sinf((float)g.t*2.2f)*(float)Dp(2.0f);
    bounds.Y += wob;

    // sombra/glow
    SolidBrush shadow(alpha(th.textShadow, alpha01));
    Rect shadowBox((INT)bounds.X - padX + 2, (INT)bounds.Y - padY + 2,
                   (INT)bounds.Width + padX*2, (INT)bounds.Height + padY*2);
    FillRoundedRectangle(&gfx, &shadow, shadowBox, Dp(14.0f));

    Pen glow(WithAlpha(kSpinB, alpha01*0.55f), (REAL)(Dp(2.0f) * kBorderScale));
    glow.SetLineJoin(LineJoinRound); glow.SetStartCap(LineCapRound); glow.SetEndCap(LineCapRound);
    SolidBrush boxB(alpha(th.bubble, alpha01));
    Rect box((INT)bounds.X - padX, (INT)bounds.Y - padY,
             (INT)bounds.Width + padX*2, (INT)bounds.Height + padY*2);
    FillRoundedRectangle(&gfx, &boxB, box, Dp(14.0f));
    DrawRoundedRectangle(&gfx, &glow, box, Dp(14.0f));

    // texto
    SolidBrush txt(alpha(th.text, alpha01));
    gfx.DrawString(text.data(), (INT)text.size(), &title, layout, &fmt, &txt);
}

// ===== 6) UPDATE / LÓGICA DE ANIMAÇÃO =============================================

static void ShowToast(const std::wstring& s){ g.toast = s; g.toastTimer = 0.f; }

static void NextPhrase(){
    g.phraseIndex = (g.phraseIndex + 1) % (int)g.phrases.size();
    g.phraseInterval = lerpf(kPhraseMinSec, kPhraseMaxSec, fhash((float)g.phraseIndex + (float)g.t));
    g.phraseTimer = 0.f; g.phraseFadingOut = false;
}

static void CycleMode(){
    int m = ((int)g.mode + 1) % 3;
    g.nextMode = (Mode)m;
    if (g.nextMode != g.mode){ g.switching = true; g.switchT = 0.f; }
}

static void ToggleTheme(){
    g.themeIndex = 1 - g.themeIndex;
    ShowToast(g.themeIndex==0 ? L"Tema: Neon Escuro" : L"Tema: Neon Claro");
}

static void UpdateState(float dt){
    if (g.paused) return;

    // Hover boost
    const float speed = g.hoverBoost ? 1.25f : 1.f;
    g.t += dt * speed;

    // Frases
    g.phraseTimer += dt;
    const float fade = kPhraseFadeSec;
    if (!g.phraseFadingOut){
        g.phraseAlpha = std::min(1.f, g.phraseAlpha + dt/fade);
        if (g.phraseTimer >= g.phraseInterval) g.phraseFadingOut = true;
    } else {
        g.phraseAlpha = std::max(0.f, g.phraseAlpha - dt/fade);
        if (g.phraseAlpha<=0.f) NextPhrase();
    }

    // Transição de modos
    if (g.switching){
        g.switchT += dt / kModeFadeSec;
        if (g.switchT >= 1.f){
            g.switching = false; g.mode = g.nextMode; g.switchT = 0.f;
            ShowToast( g.mode==Mode::Orbital ? L"Modo: Orbital"
                     : g.mode==Mode::Energy  ? L"Modo: Barra de Energia"
                                             : L"Modo: Triangulo Pulsante");
            g.savePersist();
        }
    }

    // Toast timer
    if (!g.toast.empty()){
        g.toastTimer += dt;
        if (g.toastTimer > kToastSec) g.toast.clear();
    }
}

// ===== 7) ENTRADA DO USUÁRIO =======================================================

static void OnKeyDown(WPARAM vk){
    switch (vk){
    case VK_F2: ToggleTheme(); break;
    case VK_F3: CycleMode();   break;
    case VK_F1: g.phraseFadingOut = true; break;
    case VK_SPACE: g.paused = !g.paused; ShowToast(g.paused?L"Pausado":L"Animando"); break;
    case VK_ESCAPE: PostQuitMessage(0); break; // manter ESC pra debugging
    default: break;
    }
}

static void OnMouseMove(int x, int y){
    const float cx = (float)g.cw*0.5f, cy = (float)g.ch*0.5f;
    const float dx = (float)x - cx, dy = (float)y - cy;
    const float d2 = dx*dx + dy*dy;
    const float r  = (float)Dp(140.0f);
    g.hoverBoost = (d2 < r*r);
}

// ===== Toast & HUD ================================================================

static void DrawToast(Graphics& gfx){
    if (g.toast.empty()) return;
    const float t = clampf(g.toastTimer / kToastSec, 0.f, 1.f);
    const float a = (t<0.15f) ? (t/0.15f) : (t>0.85f? (1.f - (t-0.85f)/0.15f) : 1.f);
    gfx.SetSmoothingMode(SmoothingModeHighQuality);
    gfx.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);

    FontFamily ff(L"Segoe UI");
    Font f(&ff, (REAL)Dp(13.0f), FontStyleRegular, UnitPixel);
    StringFormat fmt; fmt.SetAlignment(StringAlignmentNear); fmt.SetLineAlignment(StringAlignmentCenter);

    const RectF layout((REAL)(g.cw - Dp(320.0f)), (REAL)Dp(16.0f), (REAL)Dp(300.0f), (REAL)Dp(36.0f));
    const Rect box((INT)layout.X - Dp(10.0f), (INT)layout.Y - Dp(6.0f),
                   (INT)layout.Width + Dp(20.0f), (INT)layout.Height + Dp(12.0f));
    SolidBrush b(alpha(CurTheme().bubble, a*0.92f));
    Pen       p(WithAlpha(kSpinA, a*0.6f), (REAL)(Dp(1.5f) * kBorderScale));
    p.SetLineJoin(LineJoinRound); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    FillRoundedRectangle(&gfx, &b, box, Dp(10.0f));
    DrawRoundedRectangle(&gfx, &p, box, Dp(10.0f));

    SolidBrush txt(alpha(CurTheme().text, a));
    gfx.DrawString(g.toast.c_str(), (INT)g.toast.size(), &f, layout, &fmt, &txt);
}

static void DrawHUD(Graphics& gfx){
    if (!g.showHud) return;
    gfx.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    FontFamily ff(L"Consolas");
    Font f(&ff, (REAL)Dp(kHudFontPt), FontStyleRegular, UnitPixel);
    SolidBrush txt(alpha(CurTheme().text, 0.85f));
    wchar_t buf[256];
    swprintf(buf, 256, L"FPS: %.1f | dt: %.3f | DPI: %d | escala: %.2f | modo: %d | frase: %d",
             g.timer.smoothedFps, g.timer.dt, g.dpi, g.scale, (int)g.mode, g.phraseIndex);
    RectF rc((REAL)Dp(14.0f), (REAL)Dp(12.0f), (REAL)(g.cw - Dp(28.0f)), (REAL)Dp(30.0f));
    gfx.DrawString(buf, -1, &f, rc, nullptr, &txt);
}

// ===== 8) JANELA/LOOP DE DESENHO ===================================================

static void DrawModes(Graphics& gfx){
    const float cx = (float)g.cw*0.5f, cy = (float)g.ch*0.55f;

    auto drawOne = [&](Mode m, float a, float s){
        Matrix old; gfx.GetTransform(&old);
        gfx.TranslateTransform((REAL)cx, (REAL)cy);
        gfx.ScaleTransform(s, s);
        gfx.TranslateTransform((REAL)-cx, (REAL)-cy);

        const float t = (float)g.t * (g.hoverBoost ? 1.15f : 1.f);
        switch (m){
        case Mode::Orbital:  DrawLoading_Orbital(gfx, a, t, cx, cy); break;
        case Mode::Energy:   DrawLoading_Energy(gfx,  a, t, cx, cy); break;
        case Mode::Triangle: DrawLoading_Triangle(gfx,a, t, cx, cy); break;
        }
        gfx.SetTransform(&old);
    };

    if (g.switching){
        const float k = easeInOutQuart(g.switchT);
        drawOne(g.mode,     (1.f - k), lerpf(1.f, 0.97f, k));
        drawOne(g.nextMode, k,         lerpf(0.97f, 1.f, k));
    } else {
        drawOne(g.mode, 1.f, 1.f);
    }
}

static void Paint(HWND hWnd){
    PAINTSTRUCT ps; HDC hdc = BeginPaint(hWnd, &ps);
    HDC memDC = CreateCompatibleDC(hdc);
    HBITMAP hbmp = CreateCompatibleBitmap(hdc, g.cw, g.ch);
    HGDIOBJ old = SelectObject(memDC, hbmp);

    // Backbuffer
    Graphics gfx(memDC);
    gfx.SetCompositingMode(CompositingModeSourceOver);
    gfx.SetCompositingQuality(CompositingQualityHighQuality);
    gfx.SetSmoothingMode(SmoothingModeHighQuality);
    gfx.SetInterpolationMode(InterpolationModeHighQualityBicubic);

    if (!g.gdi.ok){
        RECT r{0,0,g.cw,g.ch};
        HBRUSH b = CreateSolidBrush(RGB(20,24,32));
        FillRect(memDC, &r, b); DeleteObject(b);
        SetBkMode(memDC, TRANSPARENT);
        SetTextColor(memDC, RGB(240,240,240));
        DrawTextW(memDC, L"GDI+ indisponivel", -1, &r, DT_CENTER|DT_VCENTER|DT_SINGLELINE);
    } else {
        DrawBackgroundRadialVignette(gfx);
        DrawNeonGlowOverlay(gfx);
        DrawModes(gfx);

        if (!g.phrases.empty()){
            const float a = easeOutCubic(clampf(g.phraseAlpha, 0.f, 1.f));
            DrawPhraseBubble(gfx, g.phrases[g.phraseIndex], a);
        }
        DrawToast(gfx);
        DrawHUD(gfx);
    }

    BitBlt(hdc, 0,0, g.cw, g.ch, memDC, 0,0, SRCCOPY);
    SelectObject(memDC, old);
    DeleteObject(hbmp);
    DeleteDC(memDC);
    EndPaint(hWnd, &ps);
}

static void SaveScreenshotPNG(){
    if (!g.gdi.ok || !g.hwnd) return;

    Bitmap bmp(g.cw, g.ch, PixelFormat32bppPARGB);
    Graphics gfx(&bmp);
    gfx.SetCompositingMode(CompositingModeSourceOver);
    gfx.SetCompositingQuality(CompositingQualityHighQuality);
    gfx.SetSmoothingMode(SmoothingModeHighQuality);
    gfx.SetInterpolationMode(InterpolationModeHighQualityBicubic);

    DrawBackgroundRadialVignette(gfx);
    DrawNeonGlowOverlay(gfx);
    DrawModes(gfx);
    if (!g.phrases.empty()){
        const float a = easeOutCubic(clampf(g.phraseAlpha, 0.f, 1.f));
        DrawPhraseBubble(gfx, g.phrases[g.phraseIndex], a);
    }
    DrawToast(gfx);
    DrawHUD(gfx);

    UINT num=0, size=0; GetImageEncodersSize(&num, &size);
    if (size==0) return;
    std::vector<BYTE> buf(size);
    ImageCodecInfo* info = reinterpret_cast<ImageCodecInfo*>(buf.data());
    GetImageEncoders(num, size, info);
    CLSID clsid{};
    for (UINT i=0;i<num;++i){
        if (wcscmp(info[i].MimeType, L"image/png")==0){ clsid = info[i].Clsid; break; }
    }
    SYSTEMTIME st; GetLocalTime(&st);
    wchar_t name[128];
    swprintf(name, 128, L"launcher_%04d%02d%02d_%02d%02d%02d.png",
             st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    bmp.Save(name, &clsid, nullptr);
    ShowToast(L"Screenshot salvo: " + std::wstring(name));
}

// ===== 9) WNDPROC / MENSAGENS ======================================================

static void UpdateDpi(HWND hwnd, int dpi){
    UNREFERENCED_PARAMETER(hwnd);
    g.dpi = dpi>0? dpi : kBaseDPI;
    g.scale = (float)g.dpi / (float)kBaseDPI;
}

static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam){
    switch (msg){
        case WM_CREATE:{
            g.hwnd = hWnd;
            // DPI
            UINT d = 0;
            if (HMODULE u = LoadLibraryW(L"user32.dll")){
                typedef UINT (WINAPI *pGetDpiForWindow)(HWND);
                auto f = (pGetDpiForWindow)GetProcAddress(u, "GetDpiForWindow");
                d = f? f(hWnd) : 0;
                FreeLibrary(u);
            }
            UpdateDpi(hWnd, d? (int)d : kBaseDPI);
            SetTimer(hWnd, kTimerFrameId, 16, nullptr);     // ~60 FPS
            SetTimer(hWnd, kTimerExitId,  kExitTimeoutMs, nullptr); // timeout 60s
            SetTimer(hWnd, kTimerProbeId, kProbeIntervalMs, nullptr); // sonda sinal da app
            SetTimer(hWnd, kTimerLaunchDelayId, kLaunchDelayMs, nullptr); // delay pra lançar app
            return 0;
        }
        case WM_PAINT: { Paint(hWnd); return 0; }
        case WM_SIZE:{
            g.cw = LOWORD(lParam);
            g.ch = HIWORD(lParam);
            InvalidateRect(hWnd, nullptr, FALSE);
            return 0;
        }
        case WM_DPICHANGED:{
            const int newDpi = HIWORD(wParam);
            UpdateDpi(hWnd, newDpi);
            RECT* prc = (RECT*)lParam;
            SetWindowPos(hWnd, nullptr, prc->left, prc->top,
                prc->right - prc->left, prc->bottom - prc->top,
                SWP_NOZORDER | SWP_NOACTIVATE);
            return 0;
        }
        case WM_ERASEBKGND: return 1; // sem flicker
        case WM_TIMER:{
            if (wParam==kTimerFrameId){
                g.timer.tick();
                UpdateState((float)g.timer.dt);
                InvalidateRect(hWnd, nullptr, FALSE);
            } else if (wParam==kTimerExitId){
                KillTimer(hWnd, kTimerExitId);
                PostQuitMessage(0);
            } else if (wParam==kTimerProbeId){
                if (CheckReadySignal()){
                    KillTimer(hWnd, kTimerExitId);
                    KillTimer(hWnd, kTimerProbeId);
                    PostQuitMessage(0);
                }
            }  else if (wParam == kTimerLaunchDelayId){
                KillTimer(hWnd, kTimerLaunchDelayId);
                LaunchMainApp();
            }

            return 0;
        }
        case WM_MOUSEMOVE:{ OnMouseMove(GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)); return 0; }
        case WM_KEYDOWN:{
            if ((GetKeyState(VK_SHIFT)&0x8000) && wParam==VK_TAB){ g.showHud = !g.showHud; InvalidateRect(hWnd,nullptr,FALSE); return 0; }
            if ((GetKeyState(VK_CONTROL)&0x8000) && wParam=='S'){ SaveScreenshotPNG(); return 0; }
            OnKeyDown(wParam); return 0;
        }
        case WM_DESTROY: {
            KillTimer(hWnd, kTimerFrameId);
            KillTimer(hWnd, kTimerExitId);
            KillTimer(hWnd, kTimerProbeId);
            if (gReadyEvent){ CloseHandle(gReadyEvent); gReadyEvent = nullptr; }
            if (gChildProc){  CloseHandle(gChildProc);  gChildProc  = nullptr; }
            PostQuitMessage(0);
            return 0;
        }
    }
    return DefWindowProcW(hWnd, msg, wParam, lParam);
}

// ===== 10) WinMain ================================================================

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int){
    // DPI Awareness
    if (HMODULE u = LoadLibraryW(L"user32.dll")){
        if (auto f = (fSetProcessDpiAwarenessContext)GetProcAddress(u, "SetProcessDpiAwarenessContext")){
            f((HANDLE)-4); // PER_MONITOR_AWARE_V2
        }
        FreeLibrary(u);
    }

    g.hinst = hInst;
    g.gdiOk = g.gdi.ok;
    g.timer.init();
    g.phrases = make_phrases();
    g.loadPersist();
    g.phraseIndex = (int)(fhash(123.456f + (float)GetTickCount64()) * (float)g.phrases.size()) % (int)g.phrases.size();

    // Classe
    WNDCLASSEXW wc{ sizeof(wc) };
    wc.style = CS_HREDRAW|CS_VREDRAW|CS_DBLCLKS;
    wc.hInstance = hInst;
    wc.lpfnWndProc = WndProc;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = nullptr;
    wc.lpszClassName = L"NeonLauncherWindow";
    RegisterClassExW(&wc);

    // Centralizar no monitor do mouse
    POINT pt{}; GetCursorPos(&pt);
    HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
    MONITORINFO mi{ sizeof(mi) }; GetMonitorInfoW(mon, &mi);

    g.cw = 1100; g.ch = 700;
    int workW = mi.rcWork.right - mi.rcWork.left;
    int workH = mi.rcWork.bottom - mi.rcWork.top;
    int x = mi.rcWork.left + (workW - g.cw)/2;
    int y = mi.rcWork.top  + (workH - g.ch)/2;

    // Borderless
    DWORD style = WS_POPUP;
    DWORD ex    = WS_EX_APPWINDOW; // aparece na taskbar
    HWND hWnd = CreateWindowExW(ex, wc.lpszClassName, L"Neon 2500 — Launcher",
        style, x, y, g.cw, g.ch, nullptr, nullptr, hInst, nullptr);

    if (!hWnd) return 0;
    ShowWindow(hWnd, SW_SHOW);
    UpdateWindow(hWnd);

    // loop
    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0) > 0){
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    g.savePersist();
    return 0;
}

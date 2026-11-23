#!/usr/bin/env python3
"""Stage recovered release assets without modifying the recovery archive."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def prepare(resources):
    source = ROOT / 'recovered/wuwa-tappo-cn-1.0.5/frontend'
    recovery = json.loads((source.parent / 'manifest.json').read_text())
    archived = {item['path'].lstrip('/'): item['sha256'] for item in recovery['resources']}
    actual = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source.rglob('*') if path.is_file()}
    if actual != archived:
        raise ValueError('Recovered frontend differs from the original extraction manifest')
    target = resources / 'original'
    shutil.copytree(source, target)
    html = (target / 'index.html').read_text()
    # HTTPS official services are available in normal mode; audit mode stays offline.
    html = html.replace('<meta charset="UTF-8" />', '''<meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self' wuwa: data: blob:; script-src 'self' wuwa: 'unsafe-inline' 'unsafe-eval' https://*.kurogame.com https://*.kurogames.com https://*.kurogames-global.com; style-src 'self' wuwa: 'unsafe-inline' https://*.kurogame.com https://*.kurogames.com; connect-src 'self' wuwa: https://*.kurogame.com https://*.kurogames.com https://*.kurogames-global.com wss://api-mc-wuwatappo.kurogames-global.com; img-src 'self' wuwa: data: blob: https:; frame-src https://*.kurogame.com https://*.kurogames.com; object-src 'none'; base-uri 'self'">''')
    html = html.replace('<div id="app"></div>', '<div id="app"></div><script src="./offline-assets.js"></script>')
    html = html.replace('</head>', '  <link rel="stylesheet" href="./macos-panel.css" />\n  </head>')
    (target / 'index.html').write_text(html)
    shutil.copy2(ROOT / 'original-adapter/macos-panel.css', target / 'macos-panel.css')
    entry = target / 'assets/index-BelNnexT.js'
    original = entry.read_text()
    staged = original
    patches = []

    # A downloaded CJK font can leave a fresh sfnt buffer in WebKit's GPU
    # process on successive redraws. Keep the release's family aliases so the
    # main window, settings and login views all resolve to the same local faces.
    stylesheet = target / 'assets/index-DMZxgGaC.css'
    css = stylesheet.read_text()
    for filename, face in [('975MaruSC-Medium-CqkJPt5f.woff2', 'PingFangSC-Medium'),
                           ('975MaruSC-Bold-iviPgHHc.woff2', 'PingFangSC-Semibold')]:
        before = f'url(./{filename}) format("woff2")'
        after = f'local("{face}")'
        if css.count(before) != 1:
            raise ValueError(f'Original font source changed: {filename}')
        css = css.replace(before, after)
        patches.append({'file': stylesheet.name, 'reason': 'Resolve Simplified Chinese fonts locally on macOS',
                        'before': before, 'after': after})
    stylesheet.write_text(css)

    def replace(before, after, reason):
        nonlocal staged
        if staged.count(before) != 1:
            raise ValueError(f'Original adapter patch drift: {reason}')
        staged = staged.replace(before, after)
        patches.append({'reason': reason, 'before': before, 'after': after})

    replace('loaderModule.init(kurodataConfig);window.kurodata=loaderModule;initTrackCommonProps();initFrontendAlertReporting();',
            'window.kurodata=macOSTracking;', 'Disable external analytics and diagnostics initialization')
    members = ['track', 'setSuperProperties', 'flush', 'getDeviceId']
    for member in members:
        before = 'loaderModule.' + member
        count = staged.count(before)
        if count == 0:
            raise ValueError(f'Telemetry adapter drift: {member}')
        staged = staged.replace(before, 'macOSTracking.' + member)
        patches.append({'reason': 'Disable outbound telemetry member', 'member': member, 'count': count})
    staged = 'const macOSTracking={track(){},setSuperProperties(){},flush(){return Promise.resolve()},getDeviceId(){return ""}};\n' + staged
    replace('isdkSrc="//pro-cdn-sdk.kurogame.com/pro/web-sdk/1.x/kr-sdk.js"',
            'isdkSrc="https://pro-cdn-sdk.kurogame.com/pro/web-sdk/1.x/kr-sdk.js"',
            'Use HTTPS SDK script instead of inheriting custom wuwa scheme')
    replace('isdkCss="//pro-cdn-sdk.kurogame.com/pro/web-sdk/1.x/style.css"',
            'isdkCss="https://pro-cdn-sdk.kurogame.com/pro/web-sdk/1.x/style.css"',
            'Use HTTPS SDK stylesheet instead of inheriting custom wuwa scheme')
    replace('function getDictionaryAssetsHost(){const e=normalizeAssetsHost(readStoredDictionaryAssetsHost());return e&&e!==dictionaryAssetsHost&&(dictionaryAssetsHost=e),dictionaryAssetsHost}',
            'function getDictionaryAssetsHost(){if(!window.__MACOS_ONLINE__)return "wuwa://app/public";const e=normalizeAssetsHost(readStoredDictionaryAssetsHost());return e&&e!==dictionaryAssetsHost&&(dictionaryAssetsHost=e),dictionaryAssetsHost||"wuwa://app/public"}', 'Use live dictionary host with archived startup/offline fallback')
    replace('function shouldDeferRemoteDictionary(){return networkSnapshot.value.status==="offline"||networkSnapshot.value.status==="reconnecting"||networkSnapshot.value.status==="degraded"}',
            'function shouldDeferRemoteDictionary(){return window.__MACOS_ONLINE__&&(networkSnapshot.value.status==="offline"||networkSnapshot.value.status==="reconnecting"||networkSnapshot.value.status==="degraded")}', 'Respect network gate only in online mode')
    replace('function atlas(){const e={loading:!1,reload:!0};return jsonpClient.get("api/common/atlas",{},e)}',
            'function atlas(){const local=()=>fetch("wuwa://app/public/atlas.json").then(r=>r.json());if(!window.__MACOS_ONLINE__)return local();return jsonpClient.get("api/common/atlas",{},{loading:!1,reload:!0}).catch(error=>{if(isNetworkApiError(error))return local();throw error})}', 'Use live public atlas and archived network-error fallback')
    network_start = staged[staged.index('function startNetworkMonitoring(){'):staged.index('function stopNetworkMonitoring(){')]
    replace(network_start, network_start.replace('function startNetworkMonitoring(){', 'function startNetworkMonitoring(){if(!window.__MACOS_ONLINE__){if(!started){started=true;setSnapshot({status:"offline",reason:"macos-local-only",retryAttempt:0})}return}'),
            'Preserve original network monitor with explicit offline audit mode')
    # Keep the existing network monitor; the new Windows collector can also be
    # called directly by request error handlers, so disable its entry point.
    diagnostics = staged[staged.index('function requestNetworkDiagnostics('):
                         staged.index('function initializeNetworkDiagnostics(')]
    replace(diagnostics, 'function requestNetworkDiagnostics(){}',
            'Disable Windows network diagnostics collection on macOS')
    replace('initializeNetworkDiagnostics(),offlineEpisodeActive=', 'offlineEpisodeActive=',
            'Do not install Windows diagnostics listeners')
    replace('function isAppUpdaterEnabled(){if(!isTauriRuntime())return!1;const e="true".toLowerCase();return e!=="false"&&e!=="0"}',
            'function isAppUpdaterEnabled(){return false}', 'Windows updater cannot install into the macOS bundle; do not claim an update check succeeded')
    replace('function buildAssetUrl(e,t){return ',
            'function buildAssetUrl(e,t){const local=window.__ORIGINAL_ASSET_MAP__?.[t.replace(/^\\//,"").split("?")[0]];if(local&&!(isLocalRoleAssetsHost(e)&&resolveLocalRoleAssetUrl(t)))return local;return ',
            'Resolve archived assets by explicit catalog mapping before original local fallback')
    # Expose original state and router only for native integration checks, no duplicated Vue implementation.
    replace('bootstrap();export{',
            '''window.__WUWA_ORIGINAL__={router,globalStore,loadDesktopCatSettings,persistDesktopCatSettings,showToast};
            async function startMacFrontend(){
                if(window.__ORIGINAL_NATIVE_LABEL__==="main"){
                    let position=null;
                    try{position=JSON.parse(localStorage.getItem("wuwatappo-main-window-outer-pos"))}catch{}
                    await window.__TAURI_INTERNALS__.invoke("restore_pet_display",{position});
                }
                await bootstrap();
            }
            startMacFrontend();export{''',
            'Expose actual original router/store for integration verification')
    # Preserve the release's synchronous token API, backed by the native Keychain.
    cookie_start = staged.index('getCookie=e=>{const t=`kuro_${e}=`')
    cookie_end = staged.index(',throttle$1=', cookie_start)
    replace(staged[cookie_start:cookie_end],
            'getCookie=e=>window.__MACOS_SESSION__.get(e),setCookie=(e,t,n)=>window.__MACOS_SESSION__.set(e,t,n)',
            'Adapt Secure cookies unsupported by custom WKURLScheme to shared Keychain session')
    replace('applyClickReportSuccess(e){const t=parseClickCount(e);this.userInfo&&(this.userInfo={...this.userInfo,total_click_count:t}),this.setLocalClickCount(0),this.serverClickSpend=0}',
            'applyClickReportSuccess(e){const t=parseClickCount(e),n=this.cumulativeClickCount,s=Math.max(this.serverClickTotal,t);this.userInfo&&(this.userInfo={...this.userInfo,total_click_count:s}),this.setLocalClickCount(isFrozenClickCount(s)?0:Math.max(0,n-s)),this.serverClickSpend=0}',
            'Keep clicks received while a report is in flight and never roll back a newer confirmed total')
    replace('r=o.preset_id??o.id,i=toFiniteNumber(o.character_asset_id)',
            'r=toFiniteNumber(o.preset_id??o.id),i=toFiniteNumber(o.character_asset_id)',
            'Preserve numeric preset IDs encoded as strings instead of replacing them with list positions')
    entry.write_text(staged)
    main_file = target / 'assets/index-BGIVWra7.js'
    main_text = main_file.read_text()
    room_drag_handlers = """let macRoomDragPointer = null;
    function beginMacRoomDrag(member, event) {
        if (!window.__MACOS_DIRECT_MOUSE__ || !event.isPrimary || event.button !== 0 ||
            macRoomDragPointer !== null || !ot.value || On.value || ln.value || vo(member.id)) return;
        const shell = event.currentTarget;
        El(member, event.clientX, event.clientY, shell);
        if (Tt.value !== member.id) return;
        macRoomDragPointer = { id: event.pointerId, shell };
        shell.setPointerCapture(event.pointerId);
        event.preventDefault();
    }
    function moveMacRoomDrag(event) {
        if (event.pointerId === macRoomDragPointer?.id && !On.value && !Wt.value) {
            rp(event.clientX, event.clientY);
        }
    }
    function finishMacRoomDrag(event) {
        if (event.pointerId !== macRoomDragPointer?.id) return;
        if (event.type === "pointerup") moveMacRoomDrag(event);
        clearMacRoomDrag();
    }
    function clearMacRoomDrag() {
        macRoomDragPointer = null;
        xl();
        Cn(false);
    }
    function removeMacRoomDragShell(vnode) {
        if (macRoomDragPointer?.shell === vnode.el) clearMacRoomDrag();
    }
    """
    for before, after, reason in [
        ('function El(e,t,o,l){', room_drag_handlers + 'function El(e,t,o,l){',
         'Drag room members through the WebKit window without global input permission'),
        ('"data-room-cat-ui-hidden":vo(o.id)?"true":"false",style:Ht(tp(o,l))',
         '"data-room-cat-ui-hidden":vo(o.id)?"true":"false",style:Ht(tp(o,l)),'
         'onPointerdown:event=>beginMacRoomDrag(o,event),onPointermove:moveMacRoomDrag,'
         'onPointerup:finishMacRoomDrag,onPointercancel:finishMacRoomDrag,'
         'onLostpointercapture:finishMacRoomDrag,onVnodeBeforeUnmount:removeMacRoomDragShell',
         'Capture the drag on the selected room member until release or cancellation'),
        ('async function fu(e,t,o,l,d){', 'async function fu(e,t,o,l,d){if(window.__MACOS_DIRECT_MOUSE__)return;',
         'Avoid dispatching duplicate local mouse gestures from the global input monitor'),
        ('{const t=Qt(e.payload.x,e.payload.y);t&&rp(t.x,t.y);return}',
         '{if(!window.__MACOS_DIRECT_MOUSE__){const t=Qt(e.payload.x,e.payload.y);t&&rp(t.x,t.y)}return}',
         'Use window pointer coordinates for room members during a macOS drag'),
        ('await fu(t,o,xt.value,Ot.value,e.payload.memberId),xl(),await xp()',
         'await fu(t,o,xt.value,Ot.value,e.payload.memberId),window.__MACOS_DIRECT_MOUSE__||xl(),await xp()',
         'Leave room member drag completion to the captured pointer event on macOS'),
    ]:
        if main_text.count(before) != 1:
            raise ValueError(f'Original pointer dispatch patch drift: {reason}')
        main_text = main_text.replace(before, after)
        patches.append({'file': main_file.name, 'reason': reason, 'before': before, 'after': after})
    reset_before = 'const Jr=new Set,Aa=new Set;'
    if main_text.count(reset_before) != 1:
        raise ValueError('Original key-state reset patch drift')
    main_text = main_text.replace(reset_before, reset_before + 'window.__MACOS_RESET_INPUT__=()=>{Jr.clear();Aa.clear();rc()};')
    game_mode_start = main_text.index('function is(e){Hn({gameMode:e})')
    game_mode_end = main_text.index('async function su(){', game_mode_start)
    game_mode_before = main_text[game_mode_start:game_mode_end]
    game_mode_after = """let followSystemGameMode=window.__MACOS_SYSTEM_GAME_MODE__?.enabled===true,systemGameModeActive=null;
    function updateSystemGameMode(state){
        if(!followSystemGameMode)systemGameModeActive=null;
        followSystemGameMode=state.enabled===true;
        if(typeof state.active==="boolean")systemGameModeActive=state.active;
        if(!followSystemGameMode){
            void kt("set_macos_effective_game_mode",{enabled:null}).catch(()=>{});
            return;
        }
        if(systemGameModeActive===null)return;
        const value=systemGameModeActive;
        Hn({gameMode:value});
        Et.value=value;
        void kt("set_macos_effective_game_mode",{enabled:value}).catch(()=>{});
        bv(value);
    }
    function receiveSystemGameMode(event){updateSystemGameMode(event.detail)}
    function is(e){
        if(followSystemGameMode)return;
        Hn({gameMode:e});
        Et.value=e;
        Tu("game_mode",e);
        bv(e);
    }
    function nm(e){
        if(followSystemGameMode||!vt().autoGameModeOnFullscreen){Kr=false;return}
        if(e!==Kr){Kr=e;if(Et.value!==e)is(e)}
    }
    function om(){is(!Et.value)}
    """
    for before, after, reason in [
        # WebKit may cache a font copy for every distinct text run. Reuse glyph runs.
        ('Me("div",Rw,Js(w.value),1)',
         'Me("div",Rw,[(Ie(!0),Ne(Ar,null,Rr(Array.from(Js(w.value)),(glyph,index)=>(Ie(),Ne("span",{key:index,style:"display:inline-block"},Js(glyph),1))),128))])',
         'Bound desktop counter font cache to individual glyphs'),
        ('xe(Oe,e=>{', 'xe(Oe,e=>{void kt("set_macos_pointer_monitoring",{enabled:!e}).catch(()=>{});',
         'Apply pointer monitoring preference changes in AppKit'),
        ('window.addEventListener("pet-toast-geometry-changed",pu);',
         'window.addEventListener("pet-toast-geometry-changed",pu);void kt("set_macos_pointer_monitoring",{enabled:!Oe.value}).catch(()=>{});',
         'Apply saved pointer monitoring preference on start'),
        (game_mode_before, game_mode_after, 'Synchronize Tappo with both system Game Mode states'),
        ('ya=await jm(e=>{Et.value=e}),', """ya=await jm(e=>{if(!followSystemGameMode)Et.value=e}),
         window.addEventListener("macos-system-game-mode",receiveSystemGameMode),
         await kt("get_macos_game_mode").then(updateSystemGameMode).catch(()=>{}),""",
         'Ignore manual mode events while following the system'),
        ('window.removeEventListener("pet-toast-geometry-changed",pu),',
         'window.removeEventListener("macos-system-game-mode",receiveSystemGameMode),window.removeEventListener("pet-toast-geometry-changed",pu),',
         'Remove the system state listener when the desktop view unmounts'),
        ('"tray-toggle-game-mode",()=>{Te()||is(!vt().gameMode)}',
         '"tray-toggle-game-mode",()=>{Te()||om()}', 'Toggle the effective mode from the tray'),
    ]:
        if main_text.count(before) != 1:
            raise ValueError(f'Original main view patch drift: {reason}')
        main_text = main_text.replace(before, after)
        patches.append({'file': main_file.name, 'reason': reason, 'before': before, 'after': after})
    main_file.write_text(main_text)
    patches.append({'reason': 'Recover key state after permission loss or sleep without inventing click counts', 'file': main_file.name, 'before': reset_before})

    panel_file = target / 'assets/index-Gk2CevxF.js'
    panel_text = panel_file.read_text()
    # Show the actual screen number during fallback. With only one screen, keep the
    # switch button available so the user can explicitly make that screen the preference.
    switch_file = target / 'assets/switchDisplayMonitor-CKvd7TTl.js'
    for path, before, after in [
        (switch_file, 'if(d.length<=1)return h("DISPLAY","switch_skipped"',
         'if(!d.length||(d.length===1&&!await u("is_pet_display_disconnected")))return h("DISPLAY","switch_skipped"'),
        (panel_file, 'B=b(1),Y=b(1)', 'B=b(1),canAdoptScreen=b(!1),Y=b(1)'),
        (panel_file, 'B.value=h.length,Y.value=await Eo(h)',
         'B.value=h.length,Y.value=await Eo(h),canAdoptScreen.value=h.length===1&&await Cs("is_pet_display_disconnected")'),
        (panel_file, 'B.value>1?(c(),y("button",{key:0,type:"button",class:"setting-btn btn-screen"',
         '(B.value>1||(B.value===1&&canAdoptScreen.value))?(c(),y("button",{key:0,type:"button",class:"setting-btn btn-screen"'),
        (panel_file, 'X.value.length<=1||await Ro()', 'await Ro()'),
    ]:
        source_text = path.read_text()
        if source_text.count(before) != 1:
            raise ValueError(f'Display switch adapter drift: {before}')
        path.write_text(source_text.replace(before, after))
        patches.append({'file': path.name, 'reason': 'Allow explicit selection after display disconnect',
                        'before': before, 'after': after})
    # Reuse the version row and status messages with the macOS Release check.
    panel_text = panel_file.read_text()
    handler_start = panel_text.index('async function tn(){')
    handler_end = panel_text.index('et(async()=>', handler_start)
    handler_before = panel_text[handler_start:handler_end]
    handler_after = """async function tn(){
        if(!re||ce.value)return;
        ce.value=true;
        ie.value=t("setting_version_checking");
        try{
            const result=await Cs("check_mac_release");
            if(result.kind==="available")ie.value=t("setting_version_new_confirm",{version:result.version});
            else if(result.kind==="none")ie.value=t("setting_version_latest",{version:result.currentVersion});
            else if(result.kind==="disabled")ie.value=t("setting_version_disabled");
            else ie.value=t("setting_version_check_failed");
        }catch{
            ie.value=t("setting_version_check_failed");
        }finally{
            ce.value=false;
        }
    }"""
    follow_row = """systemMode.value?.supported?(c(),y("div",ul,[
        e("div",dl,[
            e("div",ml,String(D.value).startsWith("zh")?"跟随 macOS 游戏模式":"Follow macOS Game Mode",1),
            e("div",vl,String(D.value).startsWith("zh")?"自动同步系统游戏模式的开启和关闭状态。":"Keep Tappo in sync when macOS Game Mode turns on or off.",1)
        ]),
        e("div",pl,[e("label",gl,[
            e("input",{type:"checkbox",checked:systemMode.value.enabled,disabled:systemModeBusy.value,
                "aria-label":String(D.value).startsWith("zh")?"跟随 macOS 游戏模式":"Follow macOS Game Mode",
                onMousedown:M(()=>{},["stop"]),onChange:setSystemMode},null,8,["checked","disabled","aria-label"]),
            e("span",{class:"setting-slider"})
        ])])
    ])):q("",!0),"""
    for before, after, reason in [
        ('set:a=>{ae({type:"set-room-id-input",value:a})}',
         'set:a=>{m.value&&(m.value={...m.value,roomIdInput:a});ae({type:"set-room-id-input",value:a})}',
         'Echo room input locally before asynchronous WK snapshot acknowledgement'),
        ('re=An(),ce=b(!1)', 're=window.__MACOS_ONLINE__===true,ce=b(!1)',
         'Enable the macOS release button only in the online edition'),
        (handler_before, handler_after, 'Check GitHub releases via the native bridge from the settings button'),
        ('function Zs(){', """const systemMode=b(null),systemModeBusy=b(false);
        let unlistenEffectiveMode;
        async function setSystemMode(event){
            systemModeBusy.value=true;
            try{systemMode.value=await Cs("set_follow_macos_game_mode",{enabled:event.target.checked})}
            catch{event.target.checked=!!systemMode.value?.enabled;$e(String(D.value).startsWith("zh")?"无法更新游戏模式设置":"Could not update Game Mode settings")}
            finally{systemModeBusy.value=false}
        }
        function reflectEffectiveMode(value){
            const effective=value??Zs().gameMode;
            if(effective!==J.value){lt=true;J.value=effective;ue(()=>{lt=false})}
        }
        function Zs(){""", 'Add macOS Game Mode setting state'),
        ('gameMode:J.value,showTaskbarIcon:', 'showTaskbarIcon:', 'Do not persist stale mode during unrelated setting changes'),
        ('st("game_mode",J.value),We(),Qn(J.value)', 'st("game_mode",J.value),Rt({gameMode:J.value}),Qn(J.value)', 'Persist manual Game Mode only on toggle'),
        ('U=!0,oe=!0,await Ct(!1),', """unlistenEffectiveMode=await Io("macos-effective-game-mode",event=>reflectEffectiveMode(event.payload));
        systemMode.value=await Cs("get_macos_game_mode").catch(()=>null);
        if(systemMode.value?.effective!=null)reflectEffectiveMode(systemMode.value.effective);
        U=!0,oe=!0;await Ct(!1),""", 'Subscribe to effective macOS Game Mode on settings mount'),
        ('gt(()=>{ct(),Ce?.()', 'gt(()=>{unlistenEffectiveMode?.();ct(),Ce?.()', 'Release the settings listener on unmount'),
        ('e("div",ul,[e("div",dl,[e("div",ml,_(i(t)("setting_auto_game_mode_fullscreen"))',
         follow_row+'e("div",ul,[e("div",dl,[e("div",ml,_(i(t)("setting_auto_game_mode_fullscreen"))', 'Show macOS Game Mode following in settings'),
        ('n[10]||(n[10]=$=>J.value=$),type:"checkbox",onMousedown:n[11]||(n[11]=M(()=>{},["stop"]))},null,544)',
         'n[10]||(n[10]=$=>J.value=$),disabled:!!systemMode.value?.enabled,type:"checkbox",onMousedown:n[11]||(n[11]=M(()=>{},["stop"]))},null,552,["disabled"])', 'Disable manual Game Mode during system following'),
        ('checked:F.value,type:"checkbox",', 'checked:F.value,disabled:!!systemMode.value?.enabled,type:"checkbox",', 'Disable fullscreen Game Mode during system following'),
        ('fl=["checked","aria-label"]', 'fl=["checked","aria-label","disabled"]', 'Update the fullscreen switch disabled state reactively'),
    ]:
        if panel_text.count(before) != 1:
            raise ValueError(f'Original panel patch drift: {reason}')
        panel_text = panel_text.replace(before, after)
        patches.append({'file': panel_file.name, 'reason': reason, 'before': before, 'after': after})
    panel_file.write_text(panel_text)
    # Keep the official selection dialog available without loading an account SDK.
    login_file = target / 'assets/login-D7Mrat3T.js'
    login_text = login_file.read_text()
    login_patches = [
        ('Oe({link:[{rel:"stylesheet",href:Pe}]',
         'window.__MACOS_ONLINE__&&Oe({link:[{rel:"stylesheet",href:Pe}]',
         'Load original authentication SDK only online'),
        ('if(i==="online"){if($(h)){je().then', 'if(window.__MACOS_ONLINE__&&i==="online"){if($(h)){je().then',
         'Keep SDK initialization and recovery offline during audit'),
        ('window.addEventListener("cat-pass-login-overlay",V),e()});',
         'window.addEventListener("cat-pass-login-overlay",V),e()||w()});',
         'Open original choice after mounting even if initial native open event preceded listeners'),
    ]
    for before, after, reason in login_patches:
        if login_text.count(before) != 1:
            raise ValueError(f'Original login placeholder patch drift: {reason}')
        login_text = login_text.replace(before, after)
        patches.append({'file': login_file.name, 'reason': reason, 'before': before, 'after': after})
    login_file.write_text(login_text)
    # Dictionaries and public gallery are official public snapshots, never simulated user inventory.
    snapshot = ROOT / 'assets/_索引/remote/metadata'
    public = target / 'public'
    public.mkdir()
    for path in snapshot.glob('dict-*.json'):
        shutil.copy2(path, public / path.name)
    shutil.copy2(snapshot / 'atlas.json', public / 'atlas.json')
    hosts = json.loads((snapshot / 'dict_host.json').read_text())
    hosts['url'] = {lang: f'wuwa://app/public/dict-{lang}.json' for lang in hosts['url']}
    (public / 'app/json-host').mkdir(parents=True)
    (public / 'app/json-host/dict_host.json').write_text(json.dumps(hosts))
    library = ROOT / 'vendor/wuwa-tappo-assets'
    catalog = json.loads((library / 'data/catalog.json').read_text())
    asset_map = {}
    folders = {'character_skin': 'character', 'accessory': 'accessory', 'emote': 'emote'}
    from urllib.parse import quote, urlsplit
    for item in catalog['items']:
        folder = folders[item['type']]
        for field, file in item['files'].items():
            rel = file['path']
            # Public gallery, role and expression resources retain purpose-specific paths.
            destination = target / 'library' / rel
            if not destination.exists():
                if hashlib.sha256((library / rel).read_bytes()).hexdigest() != file['sha256']:
                    raise ValueError(f'Archived public asset hash mismatch: {rel}')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(library / rel, destination)
            url = 'wuwa://app/library/' + quote(rel)
            if field == 'atlas':
                asset_map[f'{folder}_atlas/{item["officialFilename"]}'] = url
            elif field == 'image':
                asset_map[f'{folder}/{item["officialFilename"]}'] = url
            if file.get('sourceUrl'):
                asset_map[urlsplit(file['sourceUrl']).path.lstrip('/')] = url
    (target / 'offline-assets.js').write_text('window.__ORIGINAL_ASSET_MAP__=' + json.dumps(asset_map, ensure_ascii=False) + ';')
    shutil.copy2(ROOT / 'original-adapter/tauri.js', target / 'tauri-adapter.js')
    shutil.copy2(ROOT / 'original-adapter/audit.js', target / 'audit.js')
    shutil.copy2(ROOT / 'original-adapter/session.js', target / 'session-adapter.js')
    shutil.copy2(ROOT / 'original-adapter/socket.js', target / 'socket-adapter.js')
    inventory = []
    for path in sorted(source.rglob('*')):
        if path.is_file():
            inventory.append({'path': str(path.relative_to(source)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (target / 'adapter-manifest.json').write_text(json.dumps({'sourceFiles': inventory, 'entryPatches': patches}, ensure_ascii=False, indent=2))
    # Inventory all literal platform calls for the implementation and completion audit.
    candidates = set()
    plugins = set()
    routes = []
    for path in source.glob('assets/*.js'):
        text = path.read_text()
        plugins.update(re.findall(r'["\x27](plugin:[^"\x27`]+)["\x27]', text))
        for name in re.findall(r'\b\w+\("([a-z][a-z0-9_]+)"(?:,|\))', text):
            if '_' in name:
                candidates.add(name)
    routes = re.findall(r'\{path:"([^"\n]+)",name:"([^"\n]+)"', original)
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'build/original-inventory.json').write_text(json.dumps({
        'routes': routes, 'pluginCommands': sorted(plugins), 'candidateCommandsAndTranslationKeys': sorted(candidates)
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import sys
    prepare(Path(sys.argv[1]))

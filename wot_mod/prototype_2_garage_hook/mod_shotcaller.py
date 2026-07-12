"""Prototype 3J: focused StrongholdClanData and event-type discovery probe."""

import json
import re

TAG = '[shotcaller]'
MARKER = '_shotcaller_3j_'
SENSITIVE = re.compile(r"(?i)(access_token|token2?|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
TRACKED = {}
TIMER_SNAPSHOTS = {}
CLANS_INSPECTED = set()
WINDOW_ALIASES = ('strongholdbattleroomwindow', 'strongholdview',
                  'fortvehicleselectpopover', 'strongholdsendsinviteswindow')
IMPORTANT_EVENTS = ('vehicle', 'player', 'member', 'roster', 'slot', 'unit',
                    'battle', 'invite', 'ready')
CLAN_HINTS = ('clan', 'member', 'player', 'roster', 'slot', 'unit', 'vehicle',
              'commander', 'legionary', 'battle', 'sortie', 'division', 'level',
              'tier', 'name', 'dbid', 'account', 'rating', 'data', 'get')
MUTATING = ('set', 'change', 'join', 'leave', 'assign', 'kick', 'invite',
            'ready', 'select', 'start', 'stop', 'create', 'destroy', 'clear')


def _log(message): print(TAG + ' ' + message)
def _mask(text):
    try: return SENSITIVE.sub(r'\1\2***MASKED***', text)
    except Exception: return text
def _text(value, limit=1000):
    try: return _mask(str(value)[:limit])
    except Exception: return '<string unavailable>'
def _contains(text, hints): return any(h in text.lower() for h in hints)


def _log_value(prefix, value, limit=1000):
    line = prefix + ' type=' + type(value).__name__
    try: line += ' len=' + str(len(value))
    except Exception: pass
    _log(line + ' repr=' + _text(value, limit))
    try:
        if isinstance(value, dict):
            _log(prefix + ' keys=' + _text(sorted(value.keys())[:30], 500))
            for key, item in list(value.items())[:10]: _log_value(prefix + '[' + _text(key,100) + ']', item, 500)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value[:10]): _log_value(prefix + '[' + str(index) + ']', item, 500)
    except Exception: pass


def _safe_event_attr(event, name):
    try: return getattr(event, name)
    except Exception: return None


def _inspect_clan(clan):
    if clan is None or id(clan) in CLANS_INSPECTED: return
    CLANS_INSPECTED.add(id(clan))
    _log('clan data class: ' + clan.__class__.__name__)
    _log('clan data repr: ' + _text(clan, 1000))
    try: _log_value('clan data attr: __dict__', getattr(clan, '__dict__'), 1000)
    except Exception: pass
    try: names = sorted(dir(clan))
    except Exception: return
    for name in names:
        if name.startswith('_') or not _contains(name, CLAN_HINTS): continue
        try:
            value = getattr(clan, name)
            if callable(value):
                if name.lower().startswith(('get','is','has','can')) and not _contains(name, MUTATING):
                    try: _log_value('clan data getter: ' + name + '()', value(), 1000)
                    except Exception as error: _log('clan data getter failed: ' + name + ': ' + str(error))
            else: _log_value('clan data attr: ' + name, value, 1000)
        except Exception as error: _log('clan data attr failed: ' + name + ': ' + str(error))


def _event_context(event):
    for name in ('ctx', 'context', 'data'):
        value = _safe_event_attr(event, name)
        if value is not None: return value
    return None


def _ctx_value(ctx, name):
    if isinstance(ctx, dict): return ctx.get(name)
    return _safe_event_attr(ctx, name)


def _inspect_event(event, scope):
    event_type = _ctx_value(event, 'eventType') or _ctx_value(event, 'type') or _safe_event_attr(event, 'eventType')
    ctx = _event_context(event)
    if event_type == 'strongholdOnTimer':
        fields = tuple(_text(_ctx_value(ctx, name), 300) for name in ('maxLevel','isSortie','textid','currentBattle','isFirstBattle','forceUpdateBuildings'))
        if TIMER_SNAPSHOTS.get(id(event)) == fields: return
        TIMER_SNAPSHOTS[id(event)] = fields
        _log('stronghold status: tier=' + fields[0] + ' sortie=' + fields[1] + ' textid=' + fields[2] + ' currentBattle=' + fields[3])
    else:
        _log('stronghold event changed: eventType=' + _text(event_type, 300) + ' ctx=' + _text(ctx, 1000))
    if event_type == 'strongholdVehicleSelected':
        _log('vehicle-selection event captured')
        _log('vehicle-selection ctx: ' + _text(ctx, 2000))
    _inspect_clan(_ctx_value(ctx, 'clan'))
    if event_type != 'strongholdOnTimer' or _contains(_text(ctx,1000), IMPORTANT_EVENTS):
        try:
            for name in sorted(dir(event)):
                if name.startswith('_') or not _contains(name, CLAN_HINTS + ('ctx','args','kwargs','event','type','alias')): continue
                value = getattr(event, name)
                if callable(value) and name.lower().startswith(('get','is','has')) and not _contains(name,MUTATING): value = value()
                elif callable(value): continue
                _log_value('stronghold event attr: ' + name, value, 1000)
        except Exception as error: _log('stronghold event inspect failed: ' + str(error))


def _parse(args, kwargs):
    for value in list(args)+[kwargs]:
        if isinstance(value, dict): return value
        try:
            if isinstance(value, basestring):
                parsed=json.loads(value)
                if isinstance(parsed,dict): return parsed
        except Exception: pass
    return None


def _web_hook(class_name, method_name, original, command):
    def hooked(instance,*args,**kwargs):
        try: result=original(instance,*args,**kwargs)
        except Exception as error: _log('web original failed: '+class_name+'.'+method_name+': '+str(error)); raise
        try:
            payload=_parse(args,kwargs); text=_text(args,1500)+' | '+_text(kwargs,1500)
            if command and isinstance(payload,dict):
                params=payload.get('params') or {}; wid=payload.get('web_id') or params.get('web_id')
                if wid: TRACKED[str(wid)]=(payload.get('command'),params.get('action'))
                if payload.get('command')=='strongholds_battle': _log('stronghold command: action='+str(params.get('action'))+' web_id='+str(wid)+' unit_id='+str(params.get('unit_id'))+' periphery_id='+str(params.get('periphery_id')))
            if _contains(text,('strongholds_battle','web_id','access_token','token','unit_id')):
                _log('web response candidate: '+class_name+'.'+method_name+' '+_mask(text)[:1500])
                for wid,detail in TRACKED.items():
                    if wid in text: _log('web response matched: web_id='+wid+' action='+str(detail[1])+' payload='+_mask(text)[:1500])
        except Exception as error: _log('web inspect failed: '+str(error))
        return result
    return hooked


def _event_hook(class_name, method_name, original):
    def hooked(instance,*args,**kwargs):
        try: result=original(instance,*args,**kwargs)
        except Exception as error: _log('event original failed: '+str(error)); raise
        for value in args:
            try:
                if 'strongholdevent' in value.__class__.__name__.lower(): _inspect_event(value,args[1] if len(args)>1 else None)
            except Exception as error: _log('event inspect failed: '+str(error))
        return result
    return hooked


def _window_hook(class_name,method_name,original):
    def hooked(instance,*args,**kwargs):
        try: result=original(instance,*args,**kwargs)
        except Exception as error: _log('window original failed: '+str(error)); raise
        text=_text(instance,500)+' | '+_text(args,500)
        if _contains(text,WINDOW_ALIASES): _log('stronghold window detected: '+text[:500])
        return result
    return hooked


def _watcher_hook(class_name,method_name,original):
    def hooked(instance,*args,**kwargs):
        try: result=original(instance,*args,**kwargs)
        except Exception as error: _log('watcher original failed: '+str(error)); raise
        _log('stronghold watcher '+('started' if method_name=='start' else 'stopped'))
        return result
    return hooked


def _install(target,class_name,method_name,factory):
    try:
        marker=MARKER+method_name
        if getattr(target,marker,False): return
        original=getattr(target,method_name,None)
        if callable(original): setattr(target,method_name,factory(class_name,method_name,original)); setattr(target,marker,True)
    except Exception as error: _log('hook install failed: '+class_name+'.'+method_name+': '+str(error))


def _setup():
    for module_name in ('gui.prb_control.items.stronghold_items','gui.prb_control.items.unit_items','gui.prb_control.entities.stronghold.unit.entity','gui.prb_control.entities.stronghold.unit.vehicles_watcher'):
        try:
            module=__import__(module_name,fromlist=['*']); _log('import ok: '+module_name)
            for name in sorted(dir(module)):
                if not name.startswith('_') and _contains(name,('strongholdclandata','stronghold','roster','player','member','slot','vehicle','unit','sortie','division')): _log('stronghold candidate: '+module_name+'.'+name)
        except Exception as error: _log('import missing: '+module_name+': '+str(error))
    try:
        import gui.Scaleform.daapi.view.lobby.browser as browser
        handlers=getattr(browser,'BrowserViewWebHandlers',None); view=getattr(browser,'Browser',None)
        if handlers:
            for name in ('handleCommand','sendResponse','sendError','sendCommand','fireEvent','browserCallback','_sendResponse','_sendError','_fireEvent','_callBrowser'): _install(handlers,'BrowserViewWebHandlers',name,lambda c,n,o:_web_hook(c,n,o,n=='handleCommand'))
        if view:
            for name in ('as_sendMessageS','as_callBrowserS','onBrowserCallback','onBrowserEvent','fireEvent'): _install(view,'Browser',name,lambda c,n,o:_web_hook(c,n,o,False))
    except Exception as error: _log('browser import failed: '+str(error))
    try:
        import gui.game_control.BrowserController as controller
        for cls in ('WebBrowser','BrowserController'):
            target=getattr(controller,cls,None)
            if target:
                for name in ('sendMessage','sendResponse','sendEvent','callback','call','execute','runScript','callBrowser','_send','_callback','onCallback','onEvent'): _install(target,cls,name,lambda c,n,o:_web_hook(c,n,o,False))
    except Exception: pass
    try:
        import gui.shared.event_bus as event_bus
        target=getattr(event_bus,'EventBus',None)
        if target:
            for name in ('handleEvent','fireEvent'): _install(target,'EventBus',name,_event_hook)
    except Exception as error: _log('EventBus import failed: '+str(error))
    try:
        import frameworks.wulf.windows_system.window as windows
        target=getattr(windows,'Window',None)
        if target: _install(target,'Window','__init__',_window_hook)
    except Exception: pass
    try:
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as watcher_module
        watcher=getattr(watcher_module,'StrongholdVehiclesWatcher',None)
        if watcher:
            for name in ('start','stop'): _install(watcher,'StrongholdVehiclesWatcher',name,_watcher_hook)
    except Exception: pass


def init(): _log('loaded'); _setup()
def fini(): _log('unloaded')

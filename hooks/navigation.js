const base = Process.getModuleByName('WXWork.exe').base;
const build = __BUILD_CONFIG__;
if (Process.arch !== build.architecture) throw new Error('Unsupported process architecture');
let settings = __INITIAL_CONFIG__;
let navNames = new Set(settings.controls);
let notified = false;
Interceptor.attach(base.add(build.assistant_predicate_rva), {
  onEnter() { this.nav = this.returnAddress.equals(base.add(build.navigation_return_rva)); },
  onLeave(value) {
    if (this.nav && settings.assistant) {
      value.replace(0);
      if (!notified) { send('导航判断已关闭'); notified = true; }
    }
  }
});
const hiddenNames = new Set();
let duiObserver = Process.attachModuleObserver({
  onAdded(module) {
    if (module.name.toLowerCase() !== 'duilib.dll') return;
    for (const name of [
      '?SetVisible@CControlUI@DuiLib@@UAEX_N@Z',
      '?SetVisible@CContainerUI@DuiLib@@UAEX_N@Z'
    ]) {
      Interceptor.attach(module.getExportByName(name), {
        onEnter(args) {
          const control = this.context.ecx;
          let controlName;
          try { controlName = control.add(build.control_name_offset).readPointer().readUtf16String(); }
          catch (_) { return; }
          if (!navNames.has(controlName)) return;
          let inNavigation = false;
          try {
            let parent = control.add(build.control_parent_offset).readPointer();
            for (let depth = 0; depth < 8 && !parent.isNull(); depth++) {
              if (parent.add(build.control_name_offset).readPointer().readUtf16String() === build.navigation_container) {
                inNavigation = true; break;
              }
              parent = parent.add(build.control_parent_offset).readPointer();
            }
          } catch (_) { return; }
          if (!inNavigation) return;
          // Only change the visibility argument for the named navigation items.
          args[0] = ptr(0);
          if (!hiddenNames.has(controlName)) {
            hiddenNames.add(controlName);
            send('已隐藏导航控件：' + controlName);
          }
        }
      });
    }
  }
});
rpc.exports = {
  configure(value) {
    settings = value;
    navNames = new Set(value.controls);
    hiddenNames.clear();
    notified = false;
  },
  stop() { duiObserver.detach(); Interceptor.detachAll(); }
};

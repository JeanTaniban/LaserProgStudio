# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
import os
import sys

from .bootstrap import bootstrap
from .studio_log import init_log_file, import_report, log, log_exception, log_section


def main() -> int:
    paths = bootstrap()

    with paths.log_path.open("w", encoding="utf-8") as f:
        init_log_file(f)

        log_section("LASERPROG STUDIO V18")
        log(f"Local date       : {_dt.datetime.now().isoformat(timespec='seconds')}")
        log(f"Root              : {paths.root}")
        log(f"Toolbox dir       : {paths.toolbox_dir}")
        log(f"Generator 2D dir  : {paths.generator_2d_dir}")
        log(f"Log path          : {paths.log_path}")
        log(f"Python executable : {sys.executable}")
        log(f"Python version    : {sys.version}")
        log(f"CWD               : {os.getcwd()}")
        log(f"QT_OPENGL         : {os.environ.get('QT_OPENGL')}")

        import_report()

        try:
            # IMPORTANT: import Qt/PyVista AFTER bootstrap (ENV vars + sys.path).
            from .services.appearance_preferences import load_appearance_preferences
            from .ui.dark_theme import apply_forced_dark_theme, configure_dark_mode_before_application

            appearance = load_appearance_preferences()
            configure_dark_mode_before_application(
                force_dark_mode=appearance.force_dark_mode,
                use_native_dialogs=appearance.use_native_dialogs,
            )

            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QApplication, QSplashScreen

            from .assets import build_startup_splash_pixmap, load_studio_icon
            from .window import LaserProgStudioV18

            app = QApplication(sys.argv)
            try:
                app.setStyle("Fusion")
            except Exception:
                pass
            if appearance.force_dark_mode:
                apply_forced_dark_theme(app)
            log(
                "[UI] Appearance: "
                f"force_dark_mode={appearance.force_dark_mode} "
                f"use_native_dialogs={appearance.use_native_dialogs}"
            )
            app.setApplicationName("LaserProg Studio")
            try:
                app.setWindowIcon(load_studio_icon())
            except Exception:
                pass

            splash = None
            try:
                splash = QSplashScreen(build_startup_splash_pixmap())
                splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
                splash.show()
                # Keep the startup splash purely visual.  The boolean backend
                # still warms up below; old visible label removed: Preparing boolean engine.
                app.processEvents()
            except Exception:
                splash = None

            try:
                from .application.boolean_backend_warmup import start_boolean_backend_warmup

                start_boolean_backend_warmup()
            except Exception:
                pass

            window = LaserProgStudioV18()
            try:
                window.showMaximized()
            except Exception:
                window.show()
            if splash is not None:
                try:
                    splash.finish(window)
                except Exception:
                    try:
                        splash.close()
                    except Exception:
                        pass
            log("[APP] app.exec()")
            code = int(app.exec())
            log(f"[APP] Finished code={code}")
        except Exception:
            log_exception("main app")
            code = 3

        log_section("RESULT")
        log(f"Exit code: {code}")
        log(f"Share this log: {paths.log_path}")
        return code


__all__ = ["main"]

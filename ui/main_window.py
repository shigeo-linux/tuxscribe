import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from config import Config
from database import Database
from api_client import APIClient
from ui.sidebar import Sidebar
from ui.brief_view import BriefView
from ui.examples_view import ExamplesView
from ui.profile_view import ProfileView
from ui.chapters_view import ChaptersView
from ui.manuscript_view import ManuscriptView
from ui.phrases_view import PhrasesView
from ui.sources_view import SourcesView
from ui.export_view import ExportView
from ui.settings_dialog import SettingsDialog

STYLE_PATH = os.path.join(os.path.dirname(__file__), 'style.css')


def _load_css():
    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(STYLE_PATH)
    except Exception:
        pass
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Tuxscribe")
        self.set_default_size(1280, 820)
        self.set_position(Gtk.WindowPosition.CENTER)

        _load_css()

        self.config = Config()
        self.db = Database()
        self.api_client = APIClient(self.config)

        self._current_project_id = None
        self._build_ui()
        self.connect('delete-event', self._on_close)

    def _build_ui(self):
        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Tuxscribe")
        self.set_titlebar(header)

        # Settings button
        settings_btn = Gtk.Button()
        settings_btn.set_image(
            Gtk.Image.new_from_icon_name('preferences-system-symbolic', Gtk.IconSize.BUTTON)
        )
        settings_btn.set_tooltip_text("Settings")
        settings_btn.connect('clicked', self._on_settings)
        header.pack_end(settings_btn)

        # Main paned layout
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(paned)

        # Sidebar
        self.sidebar = Sidebar(self.db)
        self.sidebar.set_api_client(self.api_client)
        self.sidebar.connect('project-selected', self._on_project_selected)
        self.sidebar.connect('project-deleted', self._on_project_deleted)
        paned.pack1(self.sidebar, False, False)
        paned.set_position(240)

        # Right side: stack (welcome or project)
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(150)
        paned.pack2(self.content_stack, True, True)

        # Welcome screen
        welcome = self._build_welcome()
        self.content_stack.add_named(welcome, 'welcome')

        # Project notebook
        self.notebook = Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)
        self.content_stack.add_named(self.notebook, 'project')

        self._build_tabs()
        self.content_stack.set_visible_child_name('welcome')

        # API key warning bar
        self.api_warning = Gtk.InfoBar()
        self.api_warning.set_message_type(Gtk.MessageType.WARNING)
        self.api_warning.get_content_area().pack_start(
            Gtk.Label(label="No API key set. Open Settings (⚙) to add your OpenRouter API key."),
            True, True, 0
        )
        self.api_warning.add_button("Open Settings", 1)
        self.api_warning.connect('response', self._on_warning_response)
        self.api_warning.set_no_show_all(True)

        # We can't add the warning to paned, so wrap everything in a vbox
        # Reconstruct: vbox > [api_warning, paned]
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.remove(paned)
        main_vbox.pack_start(self.api_warning, False, False, 0)
        main_vbox.pack_start(paned, True, True, 0)
        self.add(main_vbox)

        self._check_api_key()

    def _build_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label(label="Tuxscribe")
        title.get_style_context().add_class('welcome-title')
        box.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="your AI writing companion for long-form fiction and non-fiction")
        subtitle.get_style_context().add_class('welcome-subtitle')
        box.pack_start(subtitle, False, False, 0)

        hint = Gtk.Label()
        hint.set_markup('<span color="#aaa">← Create a new project to get started</span>')
        box.pack_start(hint, False, False, 0)

        return box

    def _build_tabs(self):
        self.brief_view = BriefView(self.db, self.api_client)
        self.examples_view = ExamplesView(self.db, self.api_client)
        self.profile_view = ProfileView(self.db, self.api_client)
        self.phrases_view = PhrasesView(self.db)
        self.sources_view = SourcesView(self.db, self.api_client)
        self.chapters_view = ChaptersView(self.db, self.api_client)
        self.manuscript_view = ManuscriptView(self.db, self.api_client)
        self.export_view = ExportView(self.db)

        tabs = [
            (self.brief_view, "Brief"),
            (self.examples_view, "Writing Examples"),
            (self.profile_view, "Voice Profile"),
            (self.phrases_view, "Avoid Phrases"),
            (self.sources_view, "Sources"),
            (self.chapters_view, "Chapter Plan"),
            (self.manuscript_view, "Manuscript"),
            (self.export_view, "Export"),
        ]

        for view, label in tabs:
            tab_label = Gtk.Label(label=label)
            self.notebook.append_page(view, tab_label)

        self.notebook.connect('switch-page', self._on_tab_switched)

    def _on_tab_switched(self, notebook, page, page_num):
        if page == self.phrases_view:
            self.phrases_view._refresh()
            return
        if not self._current_project_id:
            return
        if page == self.profile_view:
            self.profile_view.refresh_requirements()
        elif page == self.chapters_view:
            self.chapters_view.refresh_button_state()
        elif page == self.manuscript_view:
            self.chapters_view.save_current()
            self.manuscript_view._refresh_chapter_list()

    def _on_project_selected(self, sidebar, project_id):
        self._current_project_id = project_id
        proj = self.db.get_project(project_id)
        if proj:
            self.set_title(f"Tuxscribe — {proj['name']}")

        self.brief_view.load_project(project_id)
        self.examples_view.load_project(project_id)
        self.profile_view.load_project(project_id)
        self.phrases_view.load_project(project_id)
        self.sources_view.load_project(project_id)
        self.chapters_view.load_project(project_id)
        self.manuscript_view.load_project(project_id)
        self.export_view.load_project(project_id)

        self.content_stack.set_visible_child_name('project')
        self.notebook.show_all()

    def _on_project_deleted(self, sidebar, project_id):
        if self._current_project_id == project_id:
            self._current_project_id = None
            self.set_title("Tuxscribe")
            self.content_stack.set_visible_child_name('welcome')

    def _on_settings(self, btn):
        dialog = SettingsDialog(self, self.config)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            api_key, deepseek_key, model = dialog.get_values()
            self.config.api_key = api_key
            self.config.deepseek_api_key = deepseek_key
            self.config.model = model
            self.config.save()
            self.api_client = APIClient(self.config)
            self.sidebar.set_api_client(self.api_client)
            for view in (self.brief_view, self.examples_view,
                         self.profile_view, self.chapters_view,
                         self.manuscript_view):
                view.api_client = self.api_client
            self._check_api_key()
        dialog.destroy()

    def _on_warning_response(self, bar, response_id):
        if response_id == 1:
            self._on_settings(None)

    def _check_api_key(self):
        if not self.config.api_key:
            self.api_warning.set_visible(True)
            self.api_warning.show_all()
        else:
            self.api_warning.set_visible(False)

    def _on_close(self, window, event):
        if self.manuscript_view:
            self.manuscript_view.save_current_chapter()
        return False

"""Optional Textual interface; imported only by ``recall ui``."""
from . import daemon, recipes, security


def detail_text(recipe: recipes.Recipe) -> str:
    steps = "\n".join(f"$ {step}  [{security.label(step)}]" for step in recipe.steps)
    return (
        f"{recipe.problem}\n\n{steps}\n\nConfidence: {recipe.confidence:.0%}\n"
        f"Verified: {recipe.successes} success / {recipe.failures} failure\n"
        f"Learned in: {recipe.cwd or '(any directory)'}"
    )


def runtime_status() -> str:
    running, pid = daemon.daemon_status()
    daemon_text = f"daemon running · pid {pid}" if running else "daemon stopped"
    return f"{daemon_text} · {len(recipes.all_recipes())} local recipes"


def run() -> None:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal
    from textual.widgets import DataTable, Footer, Header, Input, Static

    class RecallApp(App):
        TITLE = "recall · verified terminal fixes"
        BINDINGS = [
            Binding("ctrl+q", "quit", "Quit", priority=True),
            Binding("ctrl+r", "refresh", "Refresh", priority=True),
            Binding("ctrl+a", "apply", "Apply", priority=True),
            Binding("ctrl+c", "copy", "Copy", priority=True),
            Binding("ctrl+u", "useful", "Useful", priority=True),
            Binding("ctrl+w", "wrong", "Wrong", priority=True),
            Binding("ctrl+e", "edit", "Edit", priority=True),
            Binding("ctrl+d", "forget", "Forget", priority=True),
        ]

        selected_recipe_id: str | None = None

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Search remembered fixes…", id="search")
            with Horizontal():
                yield DataTable(id="recipes")
                yield Static("Select a recipe", id="detail")
            yield Static(runtime_status(), id="status")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#recipes", DataTable)
            table.add_columns("ID", "Confidence", "Problem")
            self.refresh_rows("")

        def refresh_rows(self, query: str) -> None:
            table = self.query_one("#recipes", DataTable)
            table.clear()
            for recipe in recipes.ranked(query):
                table.add_row(recipe.id, f"{recipe.confidence:.0%}", recipe.problem, key=recipe.id)

        def on_input_changed(self, event: Input.Changed) -> None:
            self.refresh_rows(event.value)

        def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
            recipe = recipes.get(str(event.row_key.value)) if event.row_key else None
            if recipe:
                self.selected_recipe_id = recipe.id
                self.query_one("#detail", Static).update(detail_text(recipe))

        def action_refresh(self) -> None:
            self.refresh_rows(self.query_one("#search", Input).value)
            self.query_one("#status", Static).update(runtime_status())

        def selected(self):
            return recipes.get(self.selected_recipe_id) if self.selected_recipe_id else None

        def action_apply(self) -> None:
            if self.selected():
                self.exit(f"apply:{self.selected_recipe_id}")

        def action_copy(self) -> None:
            recipe = self.selected()
            if recipe:
                self.copy_to_clipboard("\n".join(recipe.steps))
                self.notify("Fix commands copied")

        def action_useful(self) -> None:
            if self.selected_recipe_id:
                recipes.feedback(self.selected_recipe_id, True)
                self.action_refresh()

        def action_wrong(self) -> None:
            if self.selected_recipe_id:
                recipes.feedback(self.selected_recipe_id, False)
                self.action_refresh()

        def action_edit(self) -> None:
            if self.selected():
                self.exit(f"edit:{self.selected_recipe_id}")

        def action_forget(self) -> None:
            if self.selected():
                self.exit(f"forget:{self.selected_recipe_id}")

    while True:
        result = RecallApp().run()
        if not result:
            return
        action, recipe_id = result.split(":", 1)
        if action == "apply":
            from .cli import apply_recipe
            apply_recipe(recipe_id)
            return
        if action == "edit":
            from .cli import lifecycle
            lifecycle("edit", [recipe_id])
        elif action == "forget":
            if input(f"Forget {recipe_id}? [y/N] ").strip().lower() == "y":
                recipes.forget(recipe_id)

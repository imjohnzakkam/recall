"""Optional Textual interface; imported only by ``recall ui``."""
from . import recipes


def run() -> None:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import DataTable, Footer, Header, Input, Static

    class RecallApp(App):
        TITLE = "recall · verified terminal fixes"
        BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Search remembered fixes…", id="search")
            with Horizontal():
                yield DataTable(id="recipes")
                yield Static("Select a recipe", id="detail")
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
                steps = "\n".join(f"$ {step}" for step in recipe.steps)
                self.query_one("#detail", Static).update(
                    f"{recipe.problem}\n\n{steps}\n\nConfidence: {recipe.confidence:.0%}\n"
                    f"Verified: {recipe.successes} success / {recipe.failures} failure"
                )

        def action_refresh(self) -> None:
            self.refresh_rows(self.query_one("#search", Input).value)

    RecallApp().run()

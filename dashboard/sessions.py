import html
import requests

from sqlite3 import Cursor

from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.sources import ColumnDataSource
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import FileInput, Select, Spinner
from bokeh.models.widgets.markups import Div
from bokeh.models.widgets.tables import CellEditor, DataTable, TableColumn


def _file_widgets() -> (FileInput, DataTable, ColumnDataSource):
    file_input = FileInput(name='input_sst', accept='.sst', multiple=True)
    ds = ColumnDataSource(name='ds_sst', data=dict(
        files=[], names=[], notes=[]))
    dc = [
        TableColumn(field='files', title='File', editor=CellEditor()),
        TableColumn(field='names', title='Name'),
        TableColumn(field='notes', title='Note')]
    file_table = DataTable(
        name='table_sst',
        width=400,
        height=200,
        editable=True,
        auto_edit=True,
        reorderable=False,
        index_position=None,
        source=ds,
        columns=dc)
    file_input.js_on_change('filename', CustomJS(args=dict(ds=ds), code='''
        let new_data = {'files': [], 'names': [], 'notes': []};
        for (const [key, value] of Object.entries(this.filename)) {
            new_data['files'].push(value);
            new_data['names'].push(value.substring(0, value.lastIndexOf('.')) || value);
            new_data['notes'].push('');
        }
        ds.data = new_data;
        ds.change.emit();
        '''))
    return file_input, file_table, ds


def _settings_widgets() -> row:
    return row(sizing_mode='stretch_width', children=[
        column(
            Div(text="<b>&nbsp;</b>", width=130, height=31),
            Div(text="<b>Spring rate:</b>", width=130, height=31),
            Div(text="<b>HSR:</b>", width=130, height=31),
            Div(text="<b>LSR:</b>", width=130, height=31),
            Div(text="<b>LSC:</b>", width=130, height=31),
            Div(text="<b>HSC:</b>", width=130, height=31)),
        column(
            Div(text="<b>Front</b>", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130)),
        column(
            Div(text="<b>Rear</b>", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130),
            Spinner(placeholder="n/a", width=130))])


def _setups_widgets(cur: Cursor) -> Select:
    res = cur.execute('SELECT setup_id, name FROM setups')
    options = [(str(r[0]), r[1]) for r in res.fetchall()]
    return Select(
        name='select_setup',
        options=options,
        value=options[0][0])


def session_dialog(cur: Cursor, full_access: bool, api: str) -> column:
    if not full_access:
        return column(name='dialog_session', children=[
                      Div(text="Ah-ah-ah, your didn't say the magic word!")])

    files_input, files_table, files_ds = _file_widgets()
    settings_display = _settings_widgets()
    setup_select = _setups_widgets(cur)

    add_button = Button(name='button_add', label="Add", button_type='success')
    add_button.js_on_change('label', CustomJS(args=dict(), code='''
        let m = this.label.split(/ |\//);
        console.log(m);
        if (m[0] == "Done") {
            if (m[1] < m[2]) {
                alert(m[2] - m[1] + " of the " + m[2] + " sessions could not be imported!");
            }
            window.location.replace("/dashboard?session=" + this.tags[0]);
        } else if (m[0] == "Error") {
            alert("None of the SST files could be imported!");
            this.label = "Add";
        }
        '''))

    def on_addbuttonclick():
        front = settings_display.children[1].children
        rear = settings_display.children[2].children
        f_spring = front[1].value
        f_hsr = front[2].value
        f_lsr = front[3].value
        f_lsc = front[4].value
        f_hsc = front[5].value
        r_spring = rear[1].value
        r_hsr = rear[2].value
        r_lsr = rear[3].value
        r_lsc = rear[4].value
        r_hsc = rear[5].value
        settings_table = \
            f"Front: Spring = {f_spring}, " + \
            f"HSR = {f_hsr}, LSR = {f_lsr}, LSC = {f_lsc}, HSC = {f_hsc}\n" + \
            f"Rear: Spring = {r_spring}, " + \
            f"HSR = {r_hsr}, LSR = {r_lsr}, LSC = {r_lsc}, HSC = {r_hsc}"

        names, notes = files_ds.data['names'], files_ds.data['notes']
        success = 0
        for i in range(len(names)):
            description = f"{html.escape(notes[i])}\n\nSuspension settings:\n{settings_table}"
            session = dict(
                name=html.escape(names[i]),
                description=description,
                setup=int(setup_select.value),
                data=files_input.value[i])
            r = requests.put(f'{api}/session', json=session)
            if r.status_code == 201:
                add_button.tags.append(r.json()['id'])
                success += 1
        if success != 0:
            add_button.label = f"Done {success}/{len(names)}"
        else:
            add_button.label = "Error"

    add_button.on_click(on_addbuttonclick)

    return column(name='dialog_session', children=[
        files_input,
        files_table,
        settings_display,
        Div(text="<b>Setups</b>", width=200),
        setup_select,
        add_button])

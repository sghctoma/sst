import html

from datetime import datetime
from functools import partial

import requests

from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.sources import ColumnDataSource
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import FileInput, Select, Spinner
from bokeh.models.widgets.markups import Div
from bokeh.models.widgets.tables import CellEditor, DataTable, TableColumn


def session_list(sessions):
    session_rows = []
    last_day = datetime.min


    def deletesession(id):
        r = requests.delete(f'http://127.0.0.1:8080/session/{id}')
        if r.status_code == 204:
            pass #TODO: refresh page (or just the session list)


    for s in sessions:
        d = datetime.fromtimestamp(s[3])
        desc = s[2] if s[2] else f"No description for {s[1]}"
        if d.date() != last_day:
            session_rows.append(Div(text=f"<p>{d.strftime('%Y.%m.%d')}</p><hr />"))
            last_day = d.date()
        b = Button(
            label="x",
            sizing_mode='fixed',
            height=20,
            width=20,
            button_type='danger',
            css_classes=['deletebutton'])
        b.on_click(partial(deletesession, id=s[0]))
        session_rows.append(row(width=245, children=[
            Div(text=f"&nbsp;&nbsp;<a href='dashboard?session={s[0]}'>{s[1]}</a><span class='tooltiptext'>{desc}</span>",
                css_classes=['tooltip']),
            b]))
    return column(name='sessions', width=245, children=session_rows)


def file_widgets():
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


def settings_widgets():
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


def setups_widgets(cur):
    res = cur.execute('SELECT setup_id, name FROM setups')
    options = [(str(r[0]), r[1]) for r in res.fetchall()]
    return Select(
        name='select_setup',
        options=options,
        value=options[0][0])


def session_dialog(cur, full_access):
    if not full_access:
        return column(name='dialog_session', children=[
                      Div(text="Ah-ah-ah, your didn't say the magic word!")])

    files_input, files_table, files_ds = file_widgets()
    settings_display = settings_widgets()
    setup_select = setups_widgets(cur)

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
        settings_table = \
            f"Front: Spring = {front[1].value}, " + \
            f"HSR = {front[2].value}, LSR = {front[3].value}, LSC = {front[4].value}, HSC = {front[5].value}\n" + \
            f"Rear: Spring = {rear[1].value}, " + \
            f"HSR = {rear[2].value}, LSR = {rear[3].value}, LSC = {rear[4].value}, HSC = {rear[5].value}"

        names, notes = files_ds.data['names'], files_ds.data['notes']
        success = 0
        for i in range(len(names)):
            description = f"{html.escape(notes[i])}\n\nSuspension settings:\n{settings_table}"
            session = dict(
                name=html.escape(names[i]),
                description=description,
                setup=int(setup_select.value),
                data=files_input.value[i])
            r = requests.put('http://127.0.0.1:8080/session', json=session)
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

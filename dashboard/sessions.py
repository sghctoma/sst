import html
import msgpack

from datetime import datetime

import numpy as np
import requests

from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.sources import ColumnDataSource
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import FileInput, Select, Spinner, TextInput
from bokeh.models.widgets.markups import Div
from bokeh.models.widgets.tables import CellEditor, DataTable, TableColumn
from bokeh.plotting.figure import figure


def session_list(sessions):
    session_divs = []
    last_day = datetime.min
    for s in sessions:
        d = datetime.fromtimestamp(s[3])
        desc = s[2] if s[2] else f"No description for {s[1]}"
        if d.date() != last_day:
            session_divs.append(Div(text=f"<p>{d.strftime('%Y.%m.%d')}</p><hr />"))
            last_day = d.date()
        session_divs.append(Div(
            text=f"&nbsp;&nbsp;<a href='dashboard?session={s[0]}'>{s[1]}</a><span class='tooltiptext'>{desc}</span>",
            css_classes=['tooltip']))
    return column(name='sessions', children=session_divs)

def file_widgets():
    file_input = FileInput(name='input_sst', accept='.sst', multiple=True)
    ds = ColumnDataSource(name='ds_sst', data=dict(files=[], names=[], notes=[]))
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
        ''')
    )
    return file_input, file_table, ds

def settings_widgets():
    return row(sizing_mode='stretch_width', children=[
        column(
            Div(text="<b>&nbsp;</b>", width=130, height=31),
            Div(text=f"<b>Spring rate:</b>", width=130, height=31),
            Div(text=f"<b>HSR:</b>", width=130, height=31),
            Div(text=f"<b>LSR:</b>", width=130, height=31),
            Div(text=f"<b>LSC:</b>", width=130, height=31),
            Div(text=f"<b>HSC:</b>", width=130, height=31)),
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

def calibrations_widgets(cur):
    res = cur.execute('SELECT ROWID, data FROM calibrations')
    calibrations = {}
    for r in res.fetchall():
        c = msgpack.unpackb(r[1])
        calibrations[r[0]] = c
    calibrations_ds = ColumnDataSource(data=dict(data=[calibrations]))
    first_key = list(calibrations.keys())[0]
    calibrations_select = Select(name='select_cal', options=[(str(k), v['Name']) for k,v in calibrations.items()], value=str(first_key))
    first = calibrations[first_key]
    calibration_display = row(
        column(
            Div(text="<b>&nbsp;</b>", width=130),
            Div(text=f"<b>Arm:</b>", width=130),
            Div(text=f"<b>Distance:</b>", width=130),
            Div(text=f"<b>Angle:</b>", width=130),
            Div(text=f"<b>Stroke:</b>", width=130)),
        column(
            Div(text="<b>Front</b>", width=130),
            Div(text=f"{first['Front']['ArmLength']:.2f} mm", width=130),
            Div(text=f"{first['Front']['MaxDistance']:.2f} mm", width=130),
            Div(text=f"{first['Front']['StartAngle']*180/np.pi:.2f} °", width=130),
            Div(text=f"{first['Front']['MaxStroke']:.2f} mm", width=130)),
        column(
            Div(text="<b>Rear</b>", width=130),
            Div(text=f"{first['Rear']['ArmLength']:.2f} mm", width=130),
            Div(text=f"{first['Rear']['MaxDistance']:.2f} mm", width=130),
            Div(text=f"{first['Rear']['StartAngle']*180/np.pi:.2f} °", width=130),
            Div(text=f"{first['Rear']['MaxStroke']:.2f} mm", width=130)))
    calibrations_select.js_on_change('value', CustomJS(args=dict(cd=calibration_display, ds=calibrations_ds), code='''
        let v = ds.data.data[0][this.value];
        cd.children[1].children[1].text = v.Front.ArmLength.toFixed(2) + " mm";
        cd.children[1].children[2].text = v.Front.MaxDistance.toFixed(2) + " mm";
        cd.children[1].children[3].text = (v.Front.StartAngle * 180 / Math.PI).toFixed(2) + " °";
        cd.children[1].children[4].text = v.Front.MaxStroke.toFixed(2) + " mm";
        cd.children[2].children[1].text = v.Rear.ArmLength.toFixed(2) + " mm";
        cd.children[2].children[2].text = v.Rear.MaxDistance.toFixed(2) + " mm";
        cd.children[2].children[3].text = (v.Rear.StartAngle * 180 / Math.PI).toFixed(2) + " °";
        cd.children[2].children[4].text = v.Rear.MaxStroke.toFixed(2) + " mm";
        ''')
    )
    return calibrations_select, calibration_display

def linkages_widgets(cur):
    res = cur.execute('SELECT ROWID, data FROM linkages')
    linkages = {}
    for r in res.fetchall():
        l = msgpack.unpackb(r[1])
        linkages[r[0]] = l
    linkages_ds = ColumnDataSource(data=dict(data=[linkages]))
    first_key = list(linkages.keys())[0]
    linkages_select = Select(name='select_lnk', options=[(str(k), v['Name']) for k,v in linkages.items()], value=str(first_key))
    wtlr = np.array(linkages[first_key]['LeverageRatio'])
    lvrg_ds = ColumnDataSource(name='ds_lvrg', data=dict(wt=wtlr[:,0], lr=wtlr[:,1]))
    lvrg = figure(
        height=150,
        width=400,
        margin=(2,10,10,10),
        sizing_mode='fixed',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        active_inspect=None,
        tools='',
        tooltips=[("wheel travel", "@x"), ("leverage ratio", "@y")],
        output_backend='webgl')
    lvrg.line('wt', 'lr', source=lvrg_ds, line_width=2)
    linkages_select.js_on_change('value', CustomJS(args=dict(lvrg_ds=lvrg_ds, lnks_ds=linkages_ds), code='''
        let v = lnks_ds.data.data[0][this.value];
        let wt = v.LeverageRatio.map(d => d[0]);
        let lr = v.LeverageRatio.map(d => d[1]);
        lvrg_ds.data['wt'] = wt;
        lvrg_ds.data['lr'] = lr;
        lvrg_ds.change.emit();
        ''')
    )
    return linkages_select, lvrg

def session_dialog(cur, full_access):
    if not full_access:
        return column(name='dialog_session', children=[Div(text="Ah-ah-ah, your didn't say the magic word!")])

    files_input, files_table, files_ds = file_widgets()
    settings_display = settings_widgets()
    calibrations_select, calibration_display = calibrations_widgets(cur)
    linkages_select, linkage_display = linkages_widgets(cur)

    add_button = Button(name='button_add', label="Add", button_type='success')
    add_button.js_on_change('label', CustomJS(args=dict(), code='''
        console.log(this.label);
        if (this.label == "Done") {
            window.location.replace("/dashboard");
        } else if (this.label == "Error") {
            alert("Could not import SST files!");
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
        for i in range(len(names)):
            description = f"{html.escape(notes[i])}\n\nSuspension settings:\n{settings_table}"
            session = dict(
                name=html.escape(names[i]),
                description=description,
                calibration=int(calibrations_select.value),
                linkage=int(linkages_select.value),
                data=files_input.value[i])
            r = requests.put('http://127.0.0.1:8080/session', json=session)
            if r.status_code == 201:
                add_button.label = "Done"
            else:
                add_button.label = "Error"

    add_button.on_click(on_addbuttonclick)

    return column(name='dialog_session', children=[
        files_input,
        files_table,
        settings_display,
        Div(text="<b>Calibration</b>", width=200),
        calibrations_select,
        calibration_display,
        Div(text="<b>Leverage ratio</b>", width=200),
        linkages_select,
        linkage_display,
        add_button])

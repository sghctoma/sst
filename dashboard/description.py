from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import TextInput, TextAreaInput
from bokeh.models.widgets.markups import Div
from bokeh.plotting import figure


def description_figure(name: str, desc: str) -> figure:
    name_input = TextInput(
        value=name,
        disabled=True,
        sizing_mode='stretch_width',
        margin=(0, 0, 0, 0),
        styles={
            "padding": "5px",
            "width": "100%",
            "background-color": "#15191C",
            "color": "#d0d0d0"},
        stylesheets=["""
            :host input {
                color: #d0d0d0;
                background-color: #20262B;
                font-size: 110%;
            }
            :host input[disabled] {
                color: #d0d0d0;
                background-color: #20262B;
            }"""],
        tags=[name])

    desc_input = TextAreaInput(
        value=desc,
        disabled=True,
        sizing_mode='stretch_both',
        margin=(0, 0, 0, 0),
        stylesheets=["""
            :host textarea {
                color: #d0d0d0;
                background-color: #20262B;
                font-size: 110%;
                padding: 12px;
                min-height: 180px;
            }
            :host textarea[disabled] {
                color: #d0d0d0;
                background-color: #20262B;
            }"""],
        styles={
            "padding": "5px",
            "padding-top": "0px",
            "padding-bottom": "28px",
            "width": "100%",
            "height": "100%",
            "background-color": "#15191C",
            "color": "#d0d0d0"},
        tags=[desc])

    savebutton = Button(
        label="save",
        disabled=True,
        sizing_mode='fixed',
        height=25,
        width=45,
        button_type='success',
        styles={
            "position": "unset",
            "margin-left": "auto",
            "margin-right": "5px"})

    savebutton.js_on_click(CustomJS(args=dict(), code='''
        '''))

    desc_input.js_on_change('value_input', CustomJS(
        args=dict(btn=savebutton, n=name_input), code='''
        let name_changed = (n.value != n.tags[0]);
        let name_empty = (n.value == "");
        let desc_changed = (this.value_input != this.tags[0]);
        btn.disabled = name_empty || !(name_changed || desc_changed);
        '''))
    name_input.js_on_change('value_input', CustomJS(
        args=dict(btn=savebutton, d=desc_input), code='''
        let name_changed = (this.value_input != this.tags[0]);
        let name_empty = (this.value_input == "");
        let desc_changed = (d.value != d.tags[0]);
        btn.disabled = name_empty || !(name_changed || desc_changed);
        '''))
    name_input.js_on_change('tags', CustomJS(args=dict(), code='''
        document.getElementById("sname").innerHTML = this.value;
        '''))

    children = [Div(text="<h3>Notes</h3>",
                    sizing_mode='stretch_width',
                    height=25,
                    stylesheets=[":host h3 {margin-block-start: 0px;}"]),
                savebutton]
    return column(
        name='description',
        sizing_mode='stretch_both',
        min_height=275,
        children=[row(sizing_mode='stretch_width',
                      height=30,
                      margin=(0, 0, 0, 0),
                      styles={
                          "width": "100%",
                          "background-color": "#15191C",
                          "color": "#d0d0d0"},
                      children=children),
                  name_input,
                  desc_input])

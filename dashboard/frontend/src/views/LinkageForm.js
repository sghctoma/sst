var m = require("mithril")
var LinkageList = require("./LinkageList")
var Linkage = require("../models/Linkage")
var InputField = require("./InputField")
var Textarea = require("./Textarea")

var LinkageForm = {
  params: {
    name: null,
    head_angle: null,
    front_stroke: null,
    rear_stroke: null,
    data: null,
  },
  selected: 0,
  leverageFileName: null,
  onselect: (value) => {
    LinkageForm.selected = value;
    const ll = Linkage.list.get(LinkageForm.selected)
    LinkageForm.params = ll !== undefined ? {
      name: ll.name,
      head_angle: ll.head_angle,
      front_stroke: ll.front_stroke,
      rear_stroke: ll.rear_stroke,
      data: ll.data,
    } : {
      name: null,
      head_angle: null,
      front_stroke: null,
      rear_stroke: null,
      data: null,
    },
    m.redraw();
  },
  validateRange: (value, min, max) => {
    if (!value) {
      return "Required"
    }
    if (value < min || value > max) {
      return `Must be between ${min} and ${max}.`
    }
    return ""
  },
  validate: () => {
    return LinkageForm.selected !== 0 || (
           LinkageForm.validateRange(LinkageForm.params.head_angle, 45, 90) === "" &&
           LinkageForm.validateRange(LinkageForm.params.front_stroke, 0, 300) === "" &&
           LinkageForm.validateRange(LinkageForm.params.rear_stroke, 0, 200) === "" &&
           LinkageForm.validateRange(LinkageForm.params.head_angle, 45, 90) === "" &&
           LinkageForm.params.data !== null)
  },
  reset: () => {
    LinkageForm.params.name = null
    LinkageForm.params.head_angle = null
    LinkageForm.params.front_stroke = null
    LinkageForm.params.rear_stroke = null
    LinkageForm.params.data = null
    LinkageForm.selected = 0
  },
  view: function(vnode) {
    return m(".setup-page", [
      m(".setup-page-header", "Linkage"),
      m(".input-field", [
        m("label", {for: "linkage"}, "Linkage"),
        m(".linkage", [
          m(LinkageList, {selected: LinkageForm.selected, onselect: LinkageForm.onselect}),
        ])
      ]),
    ].concat(LinkageForm.selected == 0 ? [
      m(InputField, {
        name: "Name",
        type: "text",
        value: LinkageForm.params.name,
        oninput: (e) => (LinkageForm.params.name = e.target.value),
        validate: (value) => value ? "" : "Required",
      }),
      m(InputField, {
        name: "Head angle",
        type: "number",
        value: LinkageForm.params.head_angle,
        oninput: (e) => (LinkageForm.params.head_angle = parseFloat(e.target.value)),
        validate: (value) => LinkageForm.validateRange(value, 45, 90),
      }),
      m(InputField, {
        name: "Front stroke",
        type: "number",
        value: LinkageForm.params.front_stroke,
        oninput: (e) => (LinkageForm.params.front_stroke = parseFloat(e.target.value)),
        validate: (value) => LinkageForm.validateRange(value, 0, 300),
      }),
      m(InputField, {
        name: "Rear stroke",
        type: "number",
        value: LinkageForm.params.rear_stroke,
        oninput: (e) => (LinkageForm.params.rear_stroke = parseFloat(e.target.value)),
        validate: (value) => LinkageForm.validateRange(value, 0, 200),
      }),
      m(InputField, {
        name: "Leverage ratio",
        type: "file",
        accept: ".csv",
        style: "display: inline-block;",
        value: LinkageForm.leverageFileName,
        onchange: async (e) => {
          LinkageForm.params.data = await e.target.files[0].text()
          LinkageForm.leverageFileName = e.target.value
          m.redraw()
        },
        validate: (value) => (value ? "" : "Required"),
      }),
    ] : null))
  }
}

module.exports = LinkageForm

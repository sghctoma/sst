var m = require("mithril")
var Board = require("../models/Board")
var BoardList = require("./BoardList")
var Dialog = require("./Dialog")
var CalibrationMethodList = require("./CalibrationMethodList")
var CalibrationMethod = require("../models/CalibrationMethod")
var Setup = require("../models/Setup")

const InputField = {
  view: (vnode) => {
    const { name, type, value, oninput, validate } = vnode.attrs
    const error = validate(value)
    return m(".input-field", [
      m("label", { for: name }, name),
      m("input", {
        type,
        name,
        value,
        oninput,
        class: error && "input-error",
      }),
      error && m(".error-message", error),
    ]);
  },
}

const Textarea = {
  view: (vnode) => {
    const { name, value, oninput, validate } = vnode.attrs
    const error = validate(value)
    return m(".input-field", [
      m("label", { for: name }, name),
      m("textarea", {
        name,
        value,
        oninput,
        rows: 10,
        class: error && "input-error",
      }),
      error && m(".error-message", error),
    ]);
  },
}

var GeneralForm = {
  name: null,
  boardId: null,
  description: null,
  oninit: Setup.loadList,
  validateName: (value) => {
    return value ? "" : "Required"
  },
  validate: () => (GeneralForm.name !== null && GeneralForm.name !== ""),
  reset: () => {
    GeneralForm.name = null
    GeneralForm.boardId = null
  },
  onselect: (value) => {
    GeneralForm.boardId = value
    const present = Board.list.has(value)
    if (!present) {
      GeneralForm.description = "Not yet seen"
      return
    }
    
    const setupId = present ? Board.list.get(value).setup_id : null
    const setupName = setupId && Setup.list.has(setupId) ? Setup.list.get(setupId).name : null
    GeneralForm.description = setupName ?
      `Currently associated with ${setupName}` : 
      "Seen, but not associated with any setup"
  },
  view: function() {
    return m(".setup-page", [
      m(".setup-page-header", "General"),
      m(InputField, {
        name: "Name",
        type: "text",
        value: GeneralForm.name,
        oninput: (e) => (GeneralForm.name = e.target.value),
        validate: GeneralForm.validateName,
      }),
      m(".input-field", [
        m("label", {for: "board"}, "DAQ unit"),
        m(".board", [
          m(BoardList, {selected: GeneralForm.boardId, onselect: GeneralForm.onselect}),
          GeneralForm.description ? m(".list-description", GeneralForm.description) : null,
        ]),
      ]),
    ]);
  }
}

var LinkageForm = {
  params: {
    head_angle: null,
    front_stroke: null,
    rear_stroke: null,
    data: null
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
  validateLeverageRatio: (value) => {
    return value ? "" : "Required"
  },
  validate: () => {
    return LinkageForm.validateRange(LinkageForm.params.head_angle, 45, 90) === "" &&
           LinkageForm.validateRange(LinkageForm.params.front_stroke, 0, 300) === "" &&
           LinkageForm.validateRange(LinkageForm.params.rear_stroke, 0, 200) === "" &&
           LinkageForm.validateRange(LinkageForm.params.head_angle, 45, 90) === "" &&
           LinkageForm.validateLeverageRatio(LinkageForm.params.data) === ""
  },
  reset: () => {
    LinkageForm.params.head_angle = null
    LinkageForm.params.front_stroke = null
    LinkageForm.params.rear_stroke = null
    LinkageForm.params.data = null
  },
  view: function(vnode) {
    return m(".setup-page", [
      m(".setup-page-header", "Linkage"),
      m(InputField, {
        name: "Head angle",
        type: "number",
        value: LinkageForm.params.head_angle,
        oninput: (e) => (LinkageForm.params.head_angle = e.target.value),
        validate: (value) => LinkageForm.validateRange(value, 45, 90),
      }),
      m(InputField, {
        name: "Front stroke",
        type: "number",
        value: LinkageForm.params.front_stroke,
        oninput: (e) => (LinkageForm.params.front_stroke = e.target.value),
        validate: (value) => LinkageForm.validateRange(value, 0, 300),
      }),
      m(InputField, {
        name: "Rear stroke",
        type: "number",
        value: LinkageForm.params.rear_stroke,
        oninput: (e) => (LinkageForm.params.rear_stroke = e.target.value),
        validate: (value) => LinkageForm.validateRange(value, 0, 200),
      }),
      m(Textarea, {
        name: "Leverage ratio",
        value: LinkageForm.params.data,
        oninput: (e) => (LinkageForm.params.data = e.target.value),
        validate: LinkageForm.validateLeverageRatio,
      }),
    ]);
  }
}

class CalibrationForm {
  constructor(label) {
    this.label = label
    this.params = {}

    this.selected = 0
    this.onselect = this.onselect.bind(this);
  }
  onselect(value) {
    this.selected = value;
    const cm = CalibrationMethod.list.get(this.selected)
    this.params = {}
    if (cm !== undefined) {
      cm.properties.inputs.forEach((input) => {
        this.params[input] = null
      })
    }
    m.redraw();
  }
  validateValue(value) {
    return !value ? "Required" : ""
  }
  validate() {
    var isValid = true
    Object.entries(this.params).forEach((e) => {
      isValid = isValid && this.validateValue(e[1]) === ""
    })
    return isValid
  }
  reset() {
    this.selected = 0
    m.redraw()
  }
  view(vnode) {
    const cm = CalibrationMethod.list.get(this.selected)
    return m(".setup-page", [
      m(".setup-page-header", this.label),
      m(".input-field", [
        m("label", {for: "method"}, "Method"),
        m(".method", [
          m(CalibrationMethodList, {selected: this.selected, onselect: this.onselect}),
          cm !== undefined ? m(".list-description", cm.description) : null,
        ])
      ]),
    ].concat(cm !== undefined ? cm.properties.inputs.flatMap(input => [
        m(InputField, {
          name: input,
          type: "number",
          value: this.params[input],
          oninput: (e) => (this.params[input] = e.target.value),
          validate: (value) => this.validateValue(value),
        }),
      ]) : null)
    )
  }
}

var frontCalibrationForm = new CalibrationForm("Front calibration")
var rearCalibrationForm = new CalibrationForm("Rear calibration")

var SetupWizard = {
  error: "",
  submitted: false,
  validate: function() {
    return GeneralForm.validate() &&
           LinkageForm.validate() &&
           (frontCalibrationForm.selected !== 0 || rearCalibrationForm.selected !== 0) &&
           frontCalibrationForm.validate() &&
           rearCalibrationForm.validate()
  },
  onopen: function() {
    Setup.loadList()
    Board.loadList()
    CalibrationMethod.loadList()
  },
  onclose: function() {
    SetupWizard.error = ""
    SetupWizard.submitted = false
    GeneralForm.reset()
    LinkageForm.reset()
    frontCalibrationForm.reset()
    rearCalibrationForm.reset()
  },
  submit: async function() {
    if (!SetupWizard.validate()) {
      SetupWizard.error = "There are missing or invalid values!"
    }

    const linkageBody = LinkageForm.params
    linkageBody.name = "Linkage for " + GeneralForm.name

    const frontCalibrationBody = frontCalibrationForm.selected ? {
      name: "Front calibration for " + GeneralForm.name,
      method_id: frontCalibrationForm.selected,
      inputs: frontCalibrationForm.params,
    } : null

    const rearCalibrationBody = rearCalibrationForm.selected ? {
      name: "Rear calibration for " + GeneralForm.name,
      method_id: rearCalibrationForm.selected,
      inputs: rearCalibrationForm.params,
    } : null

    var combined = {
      name: GeneralForm.name,
      linkage: linkageBody,
      front_calibration: frontCalibrationBody,
      rear_calibration: rearCalibrationBody,
      board: {
        id: GeneralForm.boardId,
      }
    }
    Setup.putCombined(combined)
    .then((id) => {
      SetupWizard.submitted = true
      setTimeout(() => {
        SetupWizard.onclose()
        Dialog.state.closeDialog()
      }, 1000)
    })
    .catch((error) => {
      SetupWizard.error = error.response.msg
    })
  },
  view: function() {
    return m(".wizard", [
      m(".wizard-header", "New bike setup"),
      m(".wizard-body", [
        m(GeneralForm),
        m(frontCalibrationForm),
        m(rearCalibrationForm),
        m(LinkageForm),
        SetupWizard.error && m(".error-message", SetupWizard.error),
        m("button", {
            style: "margin: 0px 9px;",
            onclick: SetupWizard.submit,
            disabled: SetupWizard.submitted,
            class: SetupWizard.submitted ? "ok-message" : ""
          },
          SetupWizard.submitted ? "Setup was created successfully." : "Submit"),
      ]),
    ]);
  }
};

module.exports = SetupWizard
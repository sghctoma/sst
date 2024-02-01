var m = require("mithril")
var Board = require("../models/Board")
var BoardList = require("./BoardList")
var Dialog = require("./Dialog")
var Login = require("./Login")
var CalibrationMethodList = require("./CalibrationMethodList")
var CalibrationMethod = require("../models/CalibrationMethod")
var Setup = require("../models/Setup")
var Linkage = require("../models/Linkage")
var LinkageForm = require("./LinkageForm")
var InputField = require("./InputField")
var Textarea = require("./Textarea")

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
          step: "any",
          value: this.params[input],
          oninput: (e) => (this.params[input] = parseFloat(e.target.value)),
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
  oncreate: function(vnode) {
    SetupWizard.dialog = vnode.attrs.parentDialog
  },
  onopen: function() {
    Board.loadList()
    .catch((e) => {
      if (e.code == 401) {
        Login.forceLogout()
      }
    })
    Setup.loadList()
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
      return
    }

    var linkageBody = LinkageForm.selected
    if (linkageBody === 0) {
      linkageBody = LinkageForm.params
    }

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
    }
    if (GeneralForm.boardId) {
      combined.board = {id: GeneralForm.boardId}
    }
    Setup.putCombined(combined)
    .then((id) => {
      Linkage.loadList()
      SetupWizard.submitted = true
      setTimeout(() => {
        SetupWizard.onclose()
        SetupWizard.dialog.state.closeDialog()
      }, 1000)
    })
    .catch((error) => {
      if (error.code == 401) {
        Login.forceLogout()
      }
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

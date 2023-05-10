var m = require("mithril")
var Dialog = require("./Dialog")
var Login = require("./Login")
var LinkageForm = require("./LinkageForm")
var InputField = require("./InputField")
var Textarea = require("./Textarea")
var Linkage = require("../models/Linkage")
var Session = require("../models/Session")

var GeneralForm = {
  params: {
    name: null,
    description: null,
    timestamp: null,
    sample_rate: null,
    data: null,
  },
  sessionFileName: null,
  validate: () => {
    var isValid = true
    isValid = isValid && GeneralForm.params.name
    isValid = isValid && GeneralForm.params.timestamp
    isValid = isValid && GeneralForm.params.sample_rate > 200 && GeneralForm.params.sample_rate < 20000
    isValid = isValid && GeneralForm.params.data
    return isValid
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
  reset: () => {
    GeneralForm.params.name = null
    GeneralForm.params.description = null
    GeneralForm.params.timestamp = null
    GeneralForm.params.sample_rate = null
    GeneralForm.params.data = null
    GeneralForm.sessionFileName = null
  },
  view: function() {
    return m(".setup-page", [
      m(".setup-page-header", "General"),
      m(InputField, {
        name: "Name",
        type: "text",
        value: GeneralForm.params.name,
        oninput: (e) => (GeneralForm.params.name = e.target.value),
        validate: (value) => value ? "" : "Required",
      }),
      m(Textarea, {
        name: "Description",
        value: GeneralForm.params.description,
        oninput: (e) => (GeneralForm.params.description = e.target.value),
        validate: (value) => "",
      }),
      m(InputField, {
        name: "Start time",
        type: "datetime-local",
        step: "1",
        value: GeneralForm.params.timestamp,
        oninput: (e) => {GeneralForm.params.timestamp = e.target.value},
        validate: (value) => value ? "" : "Required",
      }),
      m(InputField, {
        name: "Sample rate",
        type: "number",
        value: GeneralForm.params.sample_rate,
        oninput: (e) => (GeneralForm.params.sample_rate = parseInt(e.target.value)),
        validate: (value) => GeneralForm.validateRange(value, 200, 20000),
      }),
      m(InputField, {
        name: "Data",
        type: "file",
        accept: ".csv",
        style: "display: inline-block;",
        value: GeneralForm.sessionFileName,
        onchange: async (e) => {
          GeneralForm.params.data = await e.target.files[0].text()
          GeneralForm.sessionFileName = e.target.value
          m.redraw()
        },
        validate: (value) => (value ? "" : "Required"),
      }),
    ]);
  }
}

var ImportWizard = {
  error: "",
  submitted: false,
  validate: function() {
    return GeneralForm.validate() &&
           LinkageForm.validate()
  },
  oncreate: function(vnode) {
    ImportWizard.dialog = vnode.attrs.parentDialog
  },
  onopen: function() {
  },
  onclose: function() {
    ImportWizard.error = ""
    ImportWizard.submitted = false
    GeneralForm.reset()
    LinkageForm.reset()
  },
  submit: async function() {
    if (!ImportWizard.validate()) {
      ImportWizard.error = "There are missing or invalid values!"
      return
    }

    var linkageId = parseInt(LinkageForm.selected)
    if (linkageId === 0) {
      linkageBody = LinkageForm.params
      try {
        linkageId = await Linkage.put(linkageBody)
      } catch (e) {
        if (e.code == 401) {
          Login.forceLogout()
        }
        ImportWizard.error = e.response.msg
        return
      }
    }

    const sessionBody = {
      name: GeneralForm.params.name,
      description: GeneralForm.params.description,
      timestamp: new Date(GeneralForm.params.timestamp) / 1000,
      sample_rate: GeneralForm.params.sample_rate,
      linkage: linkageId,
      data: GeneralForm.params.data,
    }

    Session.putNormalized(sessionBody)
    .then((id) => {
      Session.loadList()
      ImportWizard.submitted = true
      setTimeout(() => {
        ImportWizard.onclose()
        ImportWizard.dialog.state.closeDialog()
        m.redraw() // XXX Why do I need this? It's not needed in SetupWizard.
      }, 1000)
    })
    .catch((error) => {
      if (error.code == 401) {
        Login.forceLogout()
      }
      ImportWizard.error = error.response.msg
    })
  },
  view: function() {
    return m(".wizard", [
      m(".wizard-header", "Import normalized data"),
      m(".wizard-body", [
        m(GeneralForm),
        m(LinkageForm),
        ImportWizard.error && m(".error-message", ImportWizard.error),
        m("button", {
            style: "margin: 0px 9px;",
            onclick: ImportWizard.submit,
            disabled: ImportWizard.submitted,
            class: ImportWizard.submitted ? "ok-message" : ""
          },
          ImportWizard.submitted ? "Session successfully sent to processing" : "Submit"),
      ]),
    ]);
  }
};

module.exports = ImportWizard

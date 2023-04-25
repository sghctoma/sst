var m = require("mithril")
var CalibrationMethodList = require("./CalibrationMethodList")
var CalibrationMethod = require("../models/CalibrationMethod")
var Calibration = require("../models/Calibration")
var Linkage = require("../models/Linkage")
var Setup = require("../models/Setup")


var misc = {
  name: null,
  board_id: null,
  view: function() {
    return m(".setup-page", [
      m(".setup-page-header", "Miscellaneous"),
      m(".params", [
        m("label", {for: "name"}, "Name"),
        m("input", {type: "text", id: "name", onchange: function(event) {
          misc.name = event.target.value
        }}),
        m("label", {for: "daq-identifier"}, "Associate with DAQ unit"),
        m("input", {type: "text", id: "daq-identifier", onchange: function(event) {
          misc.board_id = event.target.value
        }}),
      ]),
    ]);
  }
}

var linkage = {
  params: new Map(),
  view: function(vnode) {
    return m(".setup-page", [
      m(".setup-page-header", "Linkage"),
      m(".params", [
        m("label", {for: "head-angle"}, "Head angle"),
        m("input", {type: "number", id: "head-angle", min: 0, max: 90, onchange: function(event) {
          linkage.params.set("head_angle", event.target.value)
        }}),
        m("label", {for: "front-stroke"}, "Front stroke"),
        m("input", {type: "number", id: "front-stroke", min: 0, max: 300, onchange: function(event) {
          linkage.params.set("front_stroke", event.target.value)
        }}),
        m("label", {for: "rear-stroke"}, "Rear stroke"),
        m("input", {type: "number", id: "rear-stroke", min: 0, max: 300, onchange: function(event) {
          linkage.params.set("rear_stroke", event.target.value)
        }}),
        m("label", {for: "leverage-ratio"}, "Leverage ratio"),
        m("textarea", {id: "leverage-ratio", rows: 10, onchange: function(event) {
          linkage.params.set("data", event.target.value)
        }}),
      ]),
    ]);
  }
}

class CalibrationView {
  constructor(label) {
    this.selected = null
    this.label = label
    this.params = new Map()
  }
  view(vnode) {
    return m(".setup-page", [
      m(".setup-page-header", this.label),
      m(".params", [
        m("label", {for: "method"}, "Method"),
        m(".method", [
          m(CalibrationMethodList, {component: this}),
          this.selected ? m(".method-description", this.selected.description) : null,
        ])
      ].concat(this.selected ? this.selected.properties.inputs.flatMap(input => [
        m("label", {for: input}, input),
        m("input", {type: "number", id: input, oninput: (event) => {
            this.params.set(input, event.target.value)
          }}),
      ]) : null))
    ])
  }
}

var frontCalibration = new CalibrationView("Front calibration")
var rearCalibration = new CalibrationView("Rear calibration")

var SetupWizard = {
  errors: [],
  view: function() {
    return m(".wizard", [
      m(".wizard-header", "New bike setup"),
      m(".wizard-body", [
        m(misc),
        m(frontCalibration),
        m(rearCalibration),
        m(linkage),
        
        m("button", {style: "margin: 0px 9px;", onclick: async () => {
          SetupWizard.errors = []

          const linkageBody = Object.fromEntries(linkage.params)
          linkageBody.name = "Linkage for " + misc.name

          const frontCalibrationBody = frontCalibration.selected ? {
            name: "Front calibration for " + misc.name,
            method_id: frontCalibration.selected.id,
            inputs: Object.fromEntries(frontCalibration.params),
          } : null

          const rearCalibrationBody = rearCalibration.selected ? {
            name: "Rear calibration for " + misc.name,
            method_id: rearCalibration.selected.id,
            inputs: Object.fromEntries(rearCalibration.params),
          } : null

          // Validate Setup
          if (misc.name === null) {
            SetupWizard.errors.push("Setup name is required.")
          }

          // Validate Calibrations
          if (frontCalibrationBody === null && rearCalibrationBody === null) {
            SetupWizard.errors.push("At least one calibration is required.")
          }

          const unset = (element) => element === null;
          if (frontCalibrationBody !== null && Object.values(frontCalibrationBody.inputs).some(unset)) {
            SetupWizard.errors.push("All of front calibration's inputs are required.")
          }
          if (rearCalibrationBody !== null && Object.values(rearCalibrationBody.inputs).some(unset)) {
            SetupWizard.errors.push("All of rear calibration's inputs are required.")
          }

          // Validate Linkage
          // TODO: see if making these values nullable on the DB side causes any problems
          // if (frontCalibrationBody !== null && !Object.hasOwnProperty(linkageBody, "head_angle")) {
          if (!linkageBody.hasOwnProperty("head_angle")) {
            SetupWizard.errors.push("Head angle is required.")
          }
          // if (frontCalibrationBody !== null && !linkageBody.hasOwnProperty("front_stroke")) {
          if (!linkageBody.hasOwnProperty("front_stroke")) {
            SetupWizard.errors.push("Front stroke is required.")
          }
          // if (rearCalibrationBody !== null && !linkageBody.hasOwnProperty("rear_stroke")) {
          if (!linkageBody.hasOwnProperty("rear_stroke")) {
            SetupWizard.errors.push("Rear stroke is required.")
          }
          // if (rearCalibrationBody !== null && !linkageBody.hasOwnProperty("data")) {
          if (!linkageBody.hasOwnProperty("data")) {
            SetupWizard.errors.push("Leverage ratio data is required.")
          }

          if (SetupWizard.errors.length !== 0) {
            console.log(SetupWizard.errors)
            return
          }
          // ----

          const linkageId = await Linkage.put(linkageBody)
          var frontCalibrationId = null
          if (frontCalibrationBody) {
            frontCalibrationId = await Calibration.put(frontCalibrationBody)
          }
          var rearCalibrationId = null
          if (rearCalibrationBody) {
            rearCalibrationId = await Calibration.put(rearCalibrationBody)
          }
          const setupBody = {
            name: misc.name,
            linkage_id: linkageId,
            front_calibration_id: frontCalibrationId,
            rear_calibration_id: rearCalibrationId,
          }
          const setupId = await Setup.put(setupBody)
          console.log(setupId)
        }}, "Submit"),
      ]),
    ]);
  }
};

module.exports = SetupWizard
var m = require("mithril")
var io = require("socket.io-client");
var Session = require("../models/Session")

module.exports = {
  oninit: function(vnode) {
    this.socket = io();

    this.socket.on("session_ready", function(data) {
      Session.loadList()
    });
  },

  view: function() {
    return null
  }
}

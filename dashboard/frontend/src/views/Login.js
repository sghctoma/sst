var m = require("mithril")
var Session = require("../models/Session")
var User = require("../models/User")

var Login = {
  loginError: false,
  oninit: function() {
    User.check()
    .catch(function(e) {})
  },
  onsubmit: function(event) {
    event.preventDefault();
    const formData = new FormData(event.target);   
    const username = formData.get('username')
    const password = formData.get('password')
    User.login(username, password)
    .then(function(result) {
      Login.loginError = false
      Session.current.full_access = true
    })
    .catch(function(e) {
      Login.loginError = true
    })
    m.redraw();
  },
  logout: function() {
    User.logout()
    .then(function() {
      Session.current.full_access = false
      m.redraw();
    })
  },
  view: function() {
    return User.current ?
      m('div', {style: "width: 300px;"}, [
        m('span', {style: "font-size: 14px; color: #d0d0d0;"}, `Logged in as ${User.current}`),
        m('button.button[type=button]', {
          style: "width: 100%; margin-top: 10px;",
          onclick: () => {Login.logout()},
        }, 'Log Out')
      ]) :
      m('form', {style: "width: 300px;", onsubmit: Login.onsubmit}, [
        m('input[type=text]', {
          name: "username",
          placeholder: "Username",
          autocomplete: "username",
          style: "margin: 2px; width: 100%"
        }),
        m('input[type=password]', {
          name: "password",
          placeholder: "Password",
          autocomplete: "current-password",
          style: "margin: 2px; width: 100%",
          class: Login.loginError ? "input-error" : "",
          oninput: function() {
            Login.loginError = false;
          }
        }),
        m('button.button[type=submit]', {style: "margin: 2px; width: 100%"}, 'Log In')
      ])
  }
}

module.exports = Login
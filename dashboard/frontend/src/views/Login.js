var m = require("mithril")
var Session = require("../models/Session")
var User = require("../models/User")
var InputField = require("./InputField")

var Login = {
  loginError: false,
  passwordError: false,
  changingPassword: false,
  oninit: function(vnode) {
    Login.dialog = vnode.attrs.parentDialog
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
      Login.dialog.state.closeDialog()
    })
    .catch(function(e) {
      Login.loginError = true
    })
  },
  onpwchange: function(event) {
    event.preventDefault();
    const formData = new FormData(event.target);   
    const oldPassword = formData.get('oldPassword')
    const newPassword = formData.get('newPassword')
    User.pwchange(oldPassword, newPassword)
    .then(() => {
      Login.oldPassword = ""
      Login.newPassword = ""
      Login.changingPassword = false
      Login.passwordError = false
    })
    .catch((error) => {
      Login.passwordError = true
    })
  },
  logout: function() {
    User.logout()
    .then(function() {
      Session.current.full_access = false
      Login.dialog.state.closeDialog()
    })
  },
  forceLogout: function() {
    User.logout()
    .then(function() {
      Session.current.full_access = false
      Login.dialog.state.openDialog()
    })
  },
  view: function() {
    return User.current ?
      m('div', {style: "width: 300px;"}, [
        m('span', {style: "font-size: 14px; font-weight: bold; color: #d0d0d0;"}, User.current),
        m('.route-link', {
          onclick: () => {
            Login.changingPassword = !Login.changingPassword
          },
        }, 'change password »'),
        Login.changingPassword ? m('form', {style: "width: 300px;", onsubmit: Login.onpwchange}, [
          m('input[type=text][hidden][autocomplete=username]'),
          m('input[type=password]', {
            name: "oldPassword",
            placeholder: "Old password",
            autocomplete: "current-password",
            style: "margin: 2px; width: 100%",
            class: Login.passwordError ? "input-error" : "",
            oninput: function() {
              Login.passwordError = false;
            },
          }),
          m('input[type=password]', {
            name: "newPassword",
            placeholder: "New password",
            autocomplete: "new-password",
            style: "margin: 2px; width: 100%",
            minlength: 10,
          }),
          m('button.button[type=submit]', {style: "margin: 2px; width: 100%"}, 'Confirm')
        ]) : null,
        m('button.button[type=button]', {
          onclick: () => {Login.logout()},
          style: "width: 100%; margin-top: 10px;",
        }, 'Log Out'),
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
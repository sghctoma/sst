var m = require("mithril")
var Session = require("../models/Session")
var SST = require("../models/Global")

var Login = {
  isLoggedIn: false,
  loginError: false,
  username: '',
  oninit: function() {
    m.request({
      method: 'GET',
      url: '/auth/user'
    })
    .then(function(user) {
      Login.isLoggedIn = true
      Login.username = user.username
    })
    .catch(function(e) {
      Login.isLoggedIn = false
      Login.username = ''
    })
  },
  onsubmit: function(event) {
    event.preventDefault();
    const formData = new FormData(event.target);   
    const username = formData.get('username')
    const password = formData.get('password')
    m.request({
      method: 'POST',
      url: '/auth/login',
      headers: {
        'Content-Type': 'application/json',
      },
      body: {username, password},
    })
    .then(function(result) {
      Login.isLoggedIn = true
      Login.loginError = false
      Login.username = username
      Session.current.full_access = true
      const desc = Bokeh.documents[0].get_model_by_name("description");
      desc.children[1].disabled = false;  // name input
      desc.children[2].disabled = false;  // description textarea
      // document.getElementById('drawer-toggle').checked = false
    })
    .catch(function(e) {
      Login.loginError = true
    })
    m.redraw();
  },
  view: function() {
    return Login.isLoggedIn ?
      m('div', [
        m('span', {style: "font-size: 14px; color: #d0d0d0;"}, `Logged in as ${Login.username}`),
        m('button.button[type=button]', {style: "width: 100%", onclick: () => {
          m.request({
            method: 'POST',
            url: '/auth/logout',
          })
          .then(function() {
            Login.isLoggedIn = false
            Login.username = ''
            Session.current.full_access = false
            const desc = Bokeh.documents[0].get_model_by_name("description");
            desc.children[1].disabled = true;  // name input
            desc.children[2].disabled = true;  // description textarea
            m.redraw();
          })
        }}, 'Log Out')
      ]) :
      m('form', {onsubmit: Login.onsubmit}, [
        m('input[type=text][name=username][placeholder=Username]', {style: "width: 100%"}),
        m('input[type=password][name=password][placeholder=Password]', {
          style: "width: 100%",
          class: Login.loginError ? "input-error" : "",
          oninput: function() {
            Login.loginError = false;
          }
        }),
        m('button.button[type=submit]', {style: "width: 100%"}, 'Log In')
      ])
  }
}

module.exports = Login
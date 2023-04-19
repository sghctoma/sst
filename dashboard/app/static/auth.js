async function login(username, password) {
	const params = {
		method: "POST",
		headers: {
      "Content-Type": "application/json",
		},
		body: JSON.stringify({username: username, password: password}),
	}
  const response = await fetch("/auth/login", params);
  const result = await response.json();
	location.reload();
}

async function logout() {
  await fetch("/auth/logout", {method: "POST"});
	location.reload();
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

async function makeRequestWithJWT() {
  const options = {
    method: 'post',
    credentials: 'same-origin',
    headers: {
      'X-CSRF-TOKEN': getCookie('csrf_access_token'),
    },
  };
  const response = await fetch('/protected', options);
  const result = await response.json();
  return result;
}

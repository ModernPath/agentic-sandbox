<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$Title</title>
  <style>
    :root { color-scheme: light dark; --fg:#17233a; --bg:#f4f7fb; --card:#fff; --muted:#5b6b82; --accent:#1d4ed8; --err:#b42318; }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --fg:#e6edf7; --bg:#0f172a; --card:#162238; --muted:#9fb0c7; --accent:#7aa2ff; --err:#ff8a80; } }
    body { margin:0; font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--fg); background:var(--bg); }
    main { max-width:860px; margin:0 auto; padding:24px 16px; }
    a { color:var(--accent); font-weight:600; text-decoration:none; }
    .panel { background:var(--card); border-radius:10px; padding:16px; margin-top:16px; box-shadow:0 1px 2px rgba(0,0,0,.08); }
    input, textarea, button { font:inherit; padding:8px 10px; border-radius:7px; }
    input, textarea { border:1px solid #8a97ab; background:var(--card); color:var(--fg); width:100%; box-sizing:border-box; }
    button { border:0; background:var(--accent); color:#fff; font-weight:600; cursor:pointer; }
    button.secondary { background:none; color:var(--accent); border:1px solid var(--accent); }
    button:focus-visible, input:focus-visible, textarea:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    li { padding:8px 0; border-top:1px solid #d7deea; }
    li:first-child { border-top:0; }
    .meta { color:var(--muted); font-size:13px; }
    .error { color:var(--err); font-weight:600; }
  </style>
</head>
<body>
  <main>
    <a href="/">← All agents</a>
    <h1>$Title</h1>
    <p class="meta">$description</p>
    <p id="message" role="status" aria-live="polite"></p>
    <section class="panel">
      <form id="item-form">
        <input name="title" placeholder="Title" required maxlength="200">
        <textarea name="body" rows="2" placeholder="Details (optional)" maxlength="5000"></textarea>
        <button type="submit">Add item</button>
      </form>
    </section>
    <section class="panel">
      <ul id="items"></ul>
    </section>
  </main>
  <script>
    (function () {
      var API = '/api/agents/$name';
      var message = document.getElementById('message');
      var list = document.getElementById('items');

      function say(text, isError) {
        message.textContent = text || '';
        message.className = isError ? 'error' : '';
      }

      function request(method, path, body) {
        var options = { method: method, headers: { 'X-Sandbox-Request': '1' } };
        if (body !== undefined) {
          options.headers['Content-Type'] = 'application/json';
          options.body = JSON.stringify(body);
        }
        return fetch(API + path, options).then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error(data.detail || data.error || ('Request failed (' + r.status + ')'));
            return data;
          });
        });
      }

      function render(items) {
        list.textContent = '';
        if (!items.length) {
          var empty = document.createElement('li');
          empty.textContent = 'No items yet.';
          list.appendChild(empty);
        }
        items.forEach(function (item) {
          var row = document.createElement('li');
          var title = document.createElement('strong');
          title.textContent = item.title;
          var meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = item.status + ' · ' + item.created_at.slice(0, 16).replace('T', ' ');
          var body = document.createElement('div');
          body.textContent = item.body;
          var toggle = document.createElement('button');
          toggle.type = 'button';
          toggle.className = 'secondary';
          toggle.textContent = item.status === 'open' ? 'Mark done' : 'Reopen';
          toggle.addEventListener('click', function () {
            request('PATCH', '/items/' + encodeURIComponent(item.id),
                    { status: item.status === 'open' ? 'done' : 'open' })
              .then(load).catch(function (e) { say(e.message, true); });
          });
          row.appendChild(title);
          row.appendChild(meta);
          row.appendChild(body);
          row.appendChild(toggle);
          list.appendChild(row);
        });
      }

      function load() {
        return request('GET', '/items').then(function (data) { render(data.items); })
          .catch(function (e) { say(e.message, true); });
      }

      document.getElementById('item-form').addEventListener('submit', function (event) {
        event.preventDefault();
        var form = event.target;
        request('POST', '/items', { title: form.title.value.trim(), body: form.body.value }).then(function () {
          form.reset();
          say('Item added.');
          return load();
        }).catch(function (e) { say(e.message, true); });
      });

      load();
    })();
  </script>
</body>
</html>

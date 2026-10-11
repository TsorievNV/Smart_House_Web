async function api(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const error = new Error();
        error.status = response.status;
        throw error;
    }
    const text = await response.text();
    return text ? JSON.parse(text) : null;
}
function report(error) {
    // Ошибка определяется HTTP-кодом, тело ошибки не читается и не выводится.
    console.error('HTTP', error.status);
}
document.getElementById('create-smart-device')?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button'); button.disabled = true;
    try { await api('/api/smart_devices', {method: 'POST', body: new FormData(event.target)}); location.reload(); }
    catch (error) { report(error); } finally { button.disabled = false; }
});
document.getElementById('register-user')?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button'); button.disabled = true;
    try {
        const user = await api('/api/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(Object.fromEntries(new FormData(event.target)))});
        document.getElementById('api-message').textContent = 'Пользователь ' + user.username + ' зарегистрирован';
        event.target.reset();
    } catch (error) { report(error); } finally { button.disabled = false; }
});
document.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { await api('/api/smart_devices/' + button.dataset.delete, {method: 'DELETE'}); location.reload(); }
    catch (error) { report(error); } finally { button.disabled = false; }
}));
document.querySelectorAll('[data-publish]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { const device = await api('/api/smart_devices/' + button.dataset.publish + '/publication', {method: 'PUT'}); location.href = '/smart_devices/feed?id=' + device.id; }
    catch (error) { report(error); } finally { button.disabled = false; }
}));
document.querySelectorAll('[data-like]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
        const result = await api('/api/smart_devices/' + button.dataset.like + '/likes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({value: 1 - Number(button.dataset.isLiked)})});
        button.dataset.isLiked = String(result.is_liked); button.setAttribute('aria-pressed', String(Boolean(result.is_liked)));
        button.closest('.like-block').querySelector('.like-count').textContent = result.likes_count;
    } catch (error) { report(error); } finally { button.disabled = false; }
}));

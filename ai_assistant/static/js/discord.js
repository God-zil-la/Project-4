// =====================================
// Discord Setup JavaScript
// =====================================

function showToast(message) {

    let toast = document.createElement("div");

    toast.className = "discord-toast";

    toast.innerHTML = `
        <span>✅</span>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add("show");
    });

    setTimeout(() => {

        toast.classList.remove("show");

        setTimeout(() => {

            toast.remove();

        }, 300);

    }, 2200);

}

function copyBotId() {

    navigator.clipboard.writeText(
        document.getElementById("botid").value
    );

    showToast("Bot ID copied");

}

function toggleDiscordToken() {

    const field =
        document.getElementById("discord_token");

    field.type =
        field.type === "password"
            ? "text"
            : "password";

}

document.addEventListener("DOMContentLoaded", () => {

    const tokenField =
        document.getElementById("discord_token");

    if (!tokenField)
        return;

    const wrapper = document.createElement("div");

    wrapper.className = "password-wrapper";

    tokenField.parentNode.insertBefore(
        wrapper,
        tokenField
    );

    wrapper.appendChild(tokenField);

    const btn = document.createElement("button");

    btn.type = "button";

    btn.className = "toggle-password";

    btn.innerHTML = "👁";

    btn.onclick = toggleDiscordToken;

    wrapper.appendChild(btn);

});
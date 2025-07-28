document.addEventListener("DOMContentLoaded", () => {
    const scrollToBottomBtn = document.getElementById("scroll-to-bottom-btn");
    scrollToBottomBtn.addEventListener("click", () => {
        const messagesDiv = document.getElementById("messages");
        const lastMessage = messagesDiv.lastElementChild;

        if (lastMessage) {
            lastMessage.scrollIntoView({ behavior: "smooth" });
        }
    });


    updateButtonVisibility();
});

function clearPage() {
    const messagesDiv = document.getElementById("messages");
    messagesDiv.innerHTML = "";
}

function addMessage(message, isUser = false, files) {
    const messagesDiv = document.getElementById("messages");
    const messageDiv = document.createElement("div");
    messageDiv.className = isUser ? "user-message" : "ai-message";

    const headerDiv = document.createElement("div");
    headerDiv.className = "message-header";

    if (!isUser) {
        const botIcon = document.createElement("i");
        botIcon.className = "fas fa-robot bot-icon";
        headerDiv.appendChild(botIcon);
    } else {
        const userIcon = document.createElement("i");
        userIcon.className = "fas fa-user user-icon";
        headerDiv.appendChild(userIcon);
    }

    const messageDate = new Date();
    const formattedDate = messageDate.toLocaleString("pt-BR");
    headerDiv.innerHTML += `<span class="message-date">${formattedDate}</span>`;
    messageDiv.appendChild(headerDiv);

    const messageDivContent = document.createElement("div");
    messageDivContent.className = "message-content";
    messageDiv.appendChild(messageDivContent);
    messageDivContent.innerHTML += message;

    if (files && files.length > 0) {
        const fileListDiv = document.createElement("div");
        fileListDiv.className = "file-list";

        const fileContentDiv = document.createElement("div");
        fileContentDiv.className = "file-content";

        fileContentDiv.style.display = "none";
        let currentFile = null;

        files.forEach(file => {
            const fileButton = document.createElement("button");
            fileButton.className = "file-button";
            fileButton.innerText = file.name;
            fileButton.onclick = () => {
                if (currentFile === file) {
                    fileContentDiv.style.display = fileContentDiv.style.display === "none" ? "block" : "none";
                } else {
                    fileContentDiv.innerText = file.content;
                    fileContentDiv.style.display = "block";
                    currentFile = file;
                }
            };
            fileListDiv.appendChild(fileButton);
        });
        messageDivContent.appendChild(fileListDiv);
        messageDivContent.appendChild(fileContentDiv);
    }
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messageDiv.scrollHeight;
    updateButtonVisibility();
}

function copyCode(elementId) {
    const codeContainer = document.querySelector(`#${elementId} td.code pre`);
    if (codeContainer) {
        const codeText = codeContainer.innerText || codeContainer.textContent;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(codeText).catch(err => {
                console.error("Erro ao copiar para a área de transferência: ", err);
                alert("Erro ao copiar código. Tente novamente.");
            });
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = codeText;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
            } catch (err) {
                console.error("Erro ao copiar para a área de transferência (fallback): ", err);
                alert("Erro ao copiar código. Tente novamente.");
            }
            document.body.removeChild(textArea);
        }
    } else {
        console.error(`Elemento com ID ${elementId} não encontrado.`);
        alert("Erro: código não encontrado.");
    }
}

function changeStyleSheet(css_content) {
        const existingStyle = document.getElementById('dynamic-style');
        if (existingStyle) {
            existingStyle.remove();
        }
        const styleElement = document.createElement('style');
        styleElement.id = 'dynamic-style';
        styleElement.innerHTML = `${css_content}`;
        document.head.appendChild(styleElement);
}
// list.js

// 移除其他不必要的元素（包括“打开边栏”按钮）
function removeTargetElements() {
    // 移除特定的“个人资料”按钮
    const profileButton = document.querySelector('button[aria-label="打开“个人资料”菜单"]');
    if (profileButton) {
        profileButton.remove();
    }

    // 移除特定的“画布”按钮
    const menuItems = document.querySelectorAll('div[role="menuitem"]');
    for (let item of menuItems) {
        if (item.textContent.includes('画布')) {
            item.remove();
        }
    }
    
    // 去掉<nav> </nav>这个标签
    const navigationTag = document.querySelectorAll('nav');
    for (let item of navigationTag) {
            item.remove();
    }
    // 移除包含“共享”文本的 div
    const shareDivs = document.querySelectorAll('div.flex.w-full.items-center.justify-center.gap-1\\.5');
    for (let div of shareDivs) {
        if (div.textContent.includes('共享')) {
            console.log('移除包含“共享”的 div');
            div.remove();
        }
    }

    // 移除 aria-label="yanjiu" 的按钮
    const yanjiuButton = document.querySelector('button[aria-label="yanjiu"]');
    if (yanjiuButton) {
        yanjiuButton.remove();
    }

    // 移除“打开边栏”按钮
    const sidebarButton = document.querySelector('button[aria-label="打开边栏"]');
    if (sidebarButton) {
        sidebarButton.remove();
        console.log('已移除“打开边栏”按钮');
    }

    // 移除特定的 div 元素
    const divs = document.getElementsByTagName('div');
    for (let div of divs) {
        // 移除包含“复制”按钮的 div
        if (div.className === 'flex absolute left-0 right-0 flex justify-start' &&
            div.querySelector('button[aria-label="复制"]')) {
            div.remove();
        }

        // 移除 ChatGPT 4o div
        if (div.className === 'text-token-text-secondary' &&
            div.innerHTML === 'ChatGPT <span class="text-token-text-secondary">4o</span>') {
            div.remove();
        }

        // 移除 ChatGPT copyright div
        if (div.className === '' &&
            div.innerHTML === 'ChatGPT 也可能会犯错。 | ©️ChatGPT 2023-2025') {
            div.remove();
        }

        // 移除包含“搜索”按钮的 div
        if (div.style && div.style.viewTransitionName === 'var(--vt-composer-search-action)' &&
            div.querySelector('button[aria-label="搜索"]')) {
            div.remove();
        }

        // 移除 yanjiu div
        if (div.className === 'whitespace-nowrap pl-1 pr-1 [display:--force-hide-label]' &&
            div.textContent === 'yanjiu') {
            div.remove();
        }
    }

    // 移除特定的 h1 元素
    const h1s = document.getElementsByTagName('h1');
    for (let h1 of h1s) {
        if (h1.className.includes('flex h-full items-end justify-center') &&
            h1.textContent === 'Hello, ChatGPT!') {
            h1.remove();
        }
    }

    // 移除特定的 p 元素
    const paragraphs = document.getElementsByTagName('p');
    for (let p of paragraphs) {
        if (p.className === 'text-[13px] font-normal leading-[18px] text-token-text-secondary' &&
            p.textContent === '在写作和编码中协作') {
            p.remove();
        }
    }
}

// 页面加载时立即执行一次移除操作
removeTargetElements();

// 每 0.5 秒检测并移除目标元素
setInterval(() => {
    removeTargetElements();
}, 500);

// 点击并删除特定的SVG按钮（排除“打开边栏”按钮中的SVG）
function clickAndRemoveSpecificSVG() {
    const svgs = document.getElementsByTagName('svg');
    for (let svg of svgs) {
        const paths = svg.getElementsByTagName('path');
        for (let path of paths) {
            if (path.getAttribute('d') === 'M12 12.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM8.5 14a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0Z' &&
                path.getAttribute('fill') === 'currentColor') {
                // 确保不误删“打开边栏”按钮中的SVG
                const parentButton = svg.closest('button[aria-label="打开边栏"]');
                if (!parentButton) {
                    svg.click();
                    console.log('已点击并删除特定的SVG按钮');
                    svg.remove();
                    return true; // 处理后退出循环
                }
            }
        }
    }
    return false;
}

// 页面加载时尝试点击并删除特定的SVG按钮
window.addEventListener('load', () => {
    clickAndRemoveSpecificSVG();
});

// 每 0.5 秒监控并点击删除特定的SVG按钮
setInterval(() => {
    clickAndRemoveSpecificSVG();
}, 500);

// 保留“新建聊天”按钮但禁用其新建逻辑
function disableNewChatLogic() {
    const newChatButton = document.querySelector('button[aria-label="新聊天"]');
    if (newChatButton && !newChatButton.dataset.disabled) {
        newChatButton.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
        }, { capture: true, once: true });
        newChatButton.dataset.disabled = 'true';
        console.log('“新建聊天”按钮的新建逻辑已禁用');
    }
}

// 页面加载时禁用“新建聊天”按钮逻辑
window.addEventListener('load', () => {
    disableNewChatLogic();
});

// 每 0.5 秒监控并禁用“新建聊天”按钮逻辑
setInterval(() => {
    disableNewChatLogic();
}, 500);

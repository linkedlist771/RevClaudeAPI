const inputField = $('#user-input');
const chatContainer = $('.right .top');
const sendLink = $('.write-link.send');
const loader = $('#loader');
const quirkinessLevel = $('input[name="quirkiness-level"]:checked');
const url = "https://claude3.edu.cn.ucas.life";
const route = "/api/v1/claude/chat";
const streamingUrl = `${url}${route}`;
let conversationID = null;

function ajaxCall(url, method) {
  return new Promise((resolve, reject) => {
    $.ajax({
      url: url,
      type: method,
      success: function (data) {
        resolve(data);
      },
      error: function (xhr, textStatus, errorThrown) {
        reject({ xhr, textStatus, errorThrown });
      }
    });
  });
}


async function fetchStreamData(url, element, payload) {
    const apiKey = $('#api-key').val(); // 获取用户输入的 API key
    console.log(conversationID);

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', // 指定请求体格式为 JSON
                'Authorization': apiKey
            },
            body: JSON.stringify(payload) // 将 payload 对象转换为 JSON 字符串
        });

        const reader = response.body.getReader();
        const stream = new ReadableStream({
            async start(controller) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }
                    controller.enqueue(value);
                    let text = new TextDecoder().decode(value);
                    console.log(text);
                    if (text.startsWith('<')) {
                        const regex = /<.*?>/;
                        const match = text.match(regex);
                        if (match) {
                            if (conversationID === null) {
                                conversationID = match[0].slice(1, -1);
                            }
                            // replace the match part with empty string
                            text = text.replace(regex, '');
                        }
                    }
                    // 使用marked.js将Markdown转换为HTML
                    const htmlContent = marked(text);
                    element.html(element.html() + htmlContent); // 更新HTML元素
                }
                controller.close();
                reader.releaseLock();
            }
        });
        await new Response(stream).text(); // 确保流完全处理完毕
    } catch (error) {
        console.error('Error fetching stream data:', error);
    }
}


function generatePayLoad(message) {

  const chosenModel = $("#model-select option:selected").text();
  var payload = {
    "stream": true,
    "model": chosenModel,
    "message": message
  }
    ;
  if (conversationID === null) {

  }
  else {
    payload["conversation_id"] = conversationID;
  }

  return payload;


}




async function sendMessage() {
  const apiKey = $('#api-key').val();
  if (!apiKey) {
    alert('请先输入 API key');
    return;
  }
  const message = inputField.val().trim();
  if (message) {
    loader.show();
    const userMessageElement = $('<h3></h3>').html('<span>用户：</span>' + message);
    $(".content").append(userMessageElement);
    inputField.val('');
    sendLink.addClass('disabled').css('pointer-events', 'none');
    const assistantMessageElement = $('<h3></h3>').html('<span>Assistant：</span>');
    $(".content").append(assistantMessageElement);
    const payload = generatePayLoad(message);
    console.log(payload);
    await fetchStreamData(streamingUrl, assistantMessageElement, payload)
    loader.hide();
    sendLink.removeClass('disabled').css('pointer-events', 'auto');
  }
}

inputField.on('keydown', (event) => {
  if (event.key === 'Enter') {
    sendMessage();
  }
});


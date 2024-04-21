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

function processUserInput(user_input, quirkiness_level) {
  const apiUrl = `http://127.0.0.1:27402/word/user_input_processing?user_input=${user_input}&quirkiness_level=${quirkiness_level}`;
  return ajaxCall(apiUrl, 'POST');
}


async function fetchStreamData(url, element, payload) {
    const apiKey = $('#api-key').val(); // 获取用户输入的 API key

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
          // begin with <. end with >
          if (text.startsWith('<') && text.endsWith('>')) {
            conversationID = text.slice(1, -1);
          }
          if (text.startsWith('<')) {
            // conversationID = text.slice(1, -1);
            // use regex to extract the conversation_id, which is in <> 
            const regex = /<.*?>/;
            const match = text.match(regex);
            if (match) {
              conversationID = match[0].slice(1, -1);
            }
            // replace the match part with empty string
            text = text.replace(regex, '');

          }

          element.html(element.html() + text); // 更新HTML元素


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
    // chatContainer.append(userMessageElement);
    inputField.val('');
    sendLink.addClass('disabled').css('pointer-events', 'none');

    // Assuming processUserInput() returns a Promise
    // const chatWordData = await processUserInput(message, quirkiness);
    // const chatWordResponse = chatWordData.data.response;


    // Open a new EventSource to stream data from the server
    const assistantMessageElement = $('<h3></h3>').html('<span>Assistant：</span>');
    $(".content").append(assistantMessageElement);

    const payload = generatePayLoad(message);
    console.log(payload);


    await fetchStreamData(streamingUrl, assistantMessageElement, payload)


    // const chatWordResponse = "This is a dummy response."; 
    // // console.log(chatWordResponse);

    // const assistantMessageElement = $('<h3></h3>').html('<span>Assistant：</span>' + chatWordResponse);
    // $(".content").append(assistantMessageElement);


    //chatContainer.append(assistantMessageElement);
    loader.hide();
    sendLink.removeClass('disabled').css('pointer-events', 'auto');
  }
}

inputField.on('keydown', (event) => {
  if (event.key === 'Enter') {
    sendMessage();
  }
});


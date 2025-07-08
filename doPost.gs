const g_oSheetConvID  = SpreadsheetApp.openById('1Z8ZNDA4-QTSD9lJcIDQvenK2cR6s4Fpg4OqieCF1sfc').getSheetByName('Тестирование ответов модели на вопросы пользователя');

const g_oSheetClient = SpreadsheetApp.openById('1Z8ZNDA4-QTSD9lJcIDQvenK2cR6s4Fpg4OqieCF1sfc').getSheetByName('Суммаризация закрытых обращений');
const g_promt_table = SpreadsheetApp.openById('1Z8ZNDA4-QTSD9lJcIDQvenK2cR6s4Fpg4OqieCF1sfc').getSheetByName('system_message');

const g_sAPI_KEY = "db2d904fc44eb77c0ae08e272";
const g_sOmnideskEmail = "vasiliy.tatarinov@iridiummobile.ru";



function doPost(e) {
  IR.Log("\n");
  IR.Log("message_start");

  try {
    savePostData(e);

    var now = new Date();
    now.setSeconds(now.getSeconds() + 10);
    
    ScriptApp.newTrigger('Logic')
             .timeBased()
             .at(now)
             .create();
    
    IR.Log("Time_start_Logic_function: " + now);
    
    const response = ContentService.createTextOutput('OK');
    response.setMimeType(ContentService.MimeType.TEXT);
    return response;
    
  } catch (error) {
    IR.Log("Error doPost: " + error.message);
    
    const response = ContentService.createTextOutput('Error: ' + error.message);
    response.setMimeType(ContentService.MimeType.TEXT);
    return response;
  }
}

function Logic() {
  try {
    var properties = PropertiesService.getScriptProperties();
    var postData = properties.getProperty('postData');
    if (!postData) {
      throw new Error('No postData found');
    }

    let l_oData = JSON.parse(postData);
    let l_json_object = JSON.parse(postData);
    
    IR.Log("l_oContents: " + l_oData["case_number"]);
    IR.Log("l_oContents: " + JSON.stringify(postData));
    
    if (Object.keys(l_oData).length != 1) {
      let values = Clear_text_create_embedd(l_json_object);
      IR.Log(values);
      g_oSheetConvID.appendRow(values);
      
      const lastRow = g_oSheetConvID.getLastRow();
      const range = g_oSheetConvID.getRange(lastRow, 1, 1, values.length);
      
      range.setHorizontalAlignment("left");
      range.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
        
      IR.Log("Ok");
    } else {
      var lastRow = g_promt_table.getLastRow();
      var system_gpt = g_promt_table.getRange("B" + lastRow).getValue();
      
      IR.Log(system_gpt);
      let data_inf = {"case_number": l_oData["case_number"], "system_gpt": system_gpt};
      let values = Clear_data_omni_tikets(data_inf);

      if (values != null) {
        g_oSheetClient.appendRow(values);
        const lastRow = g_oSheetConvID.getLastRow();
        const range = g_oSheetConvID.getRange(lastRow, 1, 1, values.length);
        
        range.setHorizontalAlignment("left");
        range.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
        
        IR.Log("Ok");
      }
      IR.Log(values);
    }
    var allTriggers = ScriptApp.getProjectTriggers();
    for (var i = 0; i < allTriggers.length; i++) {
      var trigger = allTriggers[i];
      if (trigger.getHandlerFunction() === 'Logic') {
        ScriptApp.deleteTrigger(trigger);
      }
    }
  } catch (error) {
    IR.Log("Error Logic: " + error);
  }
}

function savePostData(e) {
  PropertiesService.getScriptProperties().setProperty('postData', e.postData.contents);
}

function Clear_text_create_embedd(json_object) {
  var url = 'https://8eb9-95-82-199-230.ngrok-free.app/clear_text_create_embedd/';

  var options = {
    'method' : 'post',
    'contentType': 'application/json',
    'payload': json_object
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    IR.Log(response.getContentText());
    var fitback = (JSON.parse(response.getContentText()));
    IR.Log("fitback: " + fitback);
    
    var jsonObject = JSON.parse(fitback);

    var case_subject = jsonObject.case_subject;
    var message_gpt = jsonObject.message_gpt;
    var message_oper = jsonObject.message_oper;
    var case_number = jsonObject.case_number;
    var score = jsonObject.score;
    var tag = jsonObject.tag;
    var id_pinecone = jsonObject.id;
    
    case_number = "https://iridi.omnidesk.ru/staff/cases/record/" + case_number

    values = [new Date(), case_subject, message_gpt, message_oper, case_number, score, id_pinecone, tag]

    return values;
  } catch (error) {
    IR.Log('Error clear_text_create_embedd: ' + error);
    return null;
  }
}


function Clear_data_omni_tikets(data_inf) {
  var url = 'https://8eb9-95-82-199-230.ngrok-free.app/clear_data_omni_tikets/';

  try {
    var options = {
      'method': 'post',
      'contentType': 'application/json',
      'payload': data_inf
    };

    var response = UrlFetchApp.fetch(url, options);
    var fitback = JSON.parse(response.getContentText());
    Logger.log("fitback: " + JSON.stringify(fitback));
    
    var question = fitback['question'];
    var answer = fitback['answer'];
    var case_number = fitback['case_number'];
    var message_gpt = fitback["message_gpt"];
    
    var values = [message_gpt, question, answer, case_number];
    return values;
  } catch (error) {
    Logger.log('Error clear_data_omni_tikets: ' + error);
    return null;
  }
}

function ParseHtml(html) {
  html = '<div>' + html + '</div>';
  html = html.replace(/<br>/g,"");

  var document = XmlService.parse(html);

  var output = XmlService.getPrettyFormat().format(document);

  output = output.replace(/<[^>]*>/g,"");
  return output
}

function DeleteTrigger(e){
  ScriptApp.deleteTrigger(
    ScriptApp.getProjectTriggers().find(
      trigger => trigger.getUniqueId() === e.triggerUid
    )
  );
}
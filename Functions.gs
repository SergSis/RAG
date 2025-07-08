const IR = {
  Log:(val)=>{
    SpreadsheetApp.openById('1Z8ZNDA4-QTSD9lJcIDQvenK2cR6s4Fpg4OqieCF1sfc') // тут ID таблицы
    .getSheetByName('log') // тут имя листа куда сыпятся логи
    .appendRow([new Date(), `${val}`]);
  }
};
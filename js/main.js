/* stuff related to the autocomplete dropdown */

// Declare as globals. We'll init them when document has loaded.
// NOTE this is an overkill, because I can just call getElementById when needed
// BUT doing this for learning purposes (and maybe some minor efficiency gain...)
var inputField;
var selectBox;
document.addEventListener("DOMContentLoaded", function(event) {
  inputField = document.getElementById('input_field');
  selectBox = document.getElementById('select_box');
});

function inputChanged(context) {
  var val = context.value.toLowerCase();
  if(val === '') {
    selectBox.style.display = 'none';
    return;
  }
  for (var i = 0; i < selectBox.children.length; i++) {
    var item = selectBox.children[i];
    if(item.innerHTML.toLowerCase().indexOf(val) >= 0) {
      item.style.display = 'block';
      selectBox.style.display = 'block';
    } else {
      item.style.display = 'none';
    }   
  }
}
  
function optionSelect(context) {
  var val = context.innerHTML;
  inputField.value = val;
  selectBox.style.display = 'none';
}
/* ------------------------------------------ */

function showDateField() {
  document.getElementById('dateDefault').style.display = 'none';
  
  var dateField = document.getElementById('dateField');
  dateField.style.display = 'block';
  dateField.click();
  dateField.focus();
}

function showCommentField() {
  document.getElementById('commentDefault').style.display = 'none';
  
  var commentField = document.getElementById('commentField');
  commentField.style.display = 'block';
  commentField.focus();
}

function showChangeTraq() {
  document.getElementById('expTraqDefaultView').style.display = 'none';
  document.getElementById('expTraqChangeBtn').style.display = 'none';
  
  var form = document.getElementById('changeTraqForm');
  form.style.display = 'block';
  form.focus();
}

function deleteEntry(item_id) {
  var okToDelete = confirm("OK to delete entry?");
  if (okToDelete == true) {
    var ajaxRequest = new XMLHttpRequest();
    ajaxRequest.onreadystatechange = function() {
      if (ajaxRequest.readyState == 4 && ajaxRequest.status == 200) {
        // Delete the <tr> identified by item_id
        var child = document.getElementById(item_id);
        child.parentNode.removeChild(child);
      }
    };
    ajaxRequest.open('DELETE', 'entry/' + item_id);
    ajaxRequest.send(null);
  }
}

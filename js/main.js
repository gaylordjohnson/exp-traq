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

// Let's play with state management:
// Now that we have 3 query string params, it's pain in the butt 
// to manage all the permutations, so will use this global
// state object as a centralized source of truth.

// NOTE: following VSCode's suggestion to use ES2015 classes 
// (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Classes)
class State {
  constructor() {
    this.traq = null;
    this.showTopN = true;
    this.showAsTable = false;
  }
  // Exp traq name must be passed in, because it comes from the server via jinja2 
  // template and main.js doesn't have access to that.
  // The other parts of the state come from the query string
  initFromServerAndQueryString(expTraqName) {
    this.traq = expTraqName;
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('show')) {
      if (urlParams.get('show') == 'all')
        this.showTopN = false;
      else
        this.showTopN = true;
    }
    if (urlParams.has('showAs')) {
      if (urlParams.get('showAs') == 'table') 
        this.showAsTable = true;
      else
        this.showAsTable = false;
    }
  }
  reloadAsTable() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=table';
    window.location = loc;
  }
  reloadAsList() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (!this.showTopN)
      loc += '&show=all';
    loc += '&showAs=list';
    window.location = loc;
  }
  reloadShowAll() {
    let loc = '/?exp_traq_name=' + this.traq;
    loc += '&show=all';
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    window.location = loc;
  }
  reloadShowTopN() {
    let loc = '/?exp_traq_name=' + this.traq;
    if (this.showAsTable)
      loc += '&showAs=table';
    else
      loc += '&showAs=list';
    window.location = loc;    
  }
}

// Global state
var state = new State();

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
  document.getElementById('dateField').style.display = 'flex';
  document.getElementById('dateInput').focus();
}

function showCommentField() {
  document.getElementById('commentDefault').style.display = 'none';
  document.getElementById('commentField').style.display = 'flex';
  document.getElementById('commentInput').focus();
}

function showChangeTraq() {
  document.getElementById('expTraqDefaultView').style.display = 'none';
  document.getElementById('expTraqChangeBtn').style.display = 'none';
  
  var form = document.getElementById('changeTraqForm');
  form.style.display = 'block';
  document.getElementById('changeExpTraqField').focus();
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

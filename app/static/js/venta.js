function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Autocompletado de clientes ──────────────────────────────────────────────
var searchInput   = document.getElementById('clienteSearch');
var clienteIdInput = document.getElementById('clienteId');
var dropdown      = document.getElementById('clienteDropdown');
var seleccionado  = document.getElementById('clienteSeleccionado');

searchInput.addEventListener('input', function() {
  var q = this.value.toLowerCase().trim();
  dropdown.innerHTML = '';
  if (!q) { dropdown.classList.remove('open'); return; }

  var matches = CLIENTES.filter(function(c) {
    return c.nombre.toLowerCase().includes(q);
  }).slice(0, 8);

  if (!matches.length) { dropdown.classList.remove('open'); return; }

  matches.forEach(function(c) {
    var div = document.createElement('div');
    div.className = 'dropdown-item';
    div.innerHTML = escapeHtml(c.nombre) + (c.tel ? ' <small>' + escapeHtml(c.tel) + '</small>' : '');
    div.addEventListener('click', function() { seleccionarCliente(c); });
    dropdown.appendChild(div);
  });
  dropdown.classList.add('open');
});

function seleccionarCliente(c) {
  clienteIdInput.value = c.id;
  searchInput.value = '';
  dropdown.classList.remove('open');
  seleccionado.style.display = 'flex';
  seleccionado.innerHTML =
    '<span>👤 <strong>' + escapeHtml(c.nombre) + '</strong>' + (c.tel ? ' · ' + escapeHtml(c.tel) : '') + '</span>' +
    '<button type="button" onclick="limpiarCliente()">✕</button>';
}

function limpiarCliente() {
  clienteIdInput.value = '';
  seleccionado.style.display = 'none';
  seleccionado.innerHTML = '';
}

document.addEventListener('click', function(e) {
  if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
    dropdown.classList.remove('open');
  }
});

// Preseleccionar cliente desde URL ?cliente_id=
var urlParams = new URLSearchParams(window.location.search);
var cliParam = urlParams.get('cliente_id');
if (cliParam) {
  var c = CLIENTES.find(function(x) { return x.id == cliParam; });
  if (c) seleccionarCliente(c);
}

// ── Items de la venta ───────────────────────────────────────────────────────
var items = [];

function agregarItem(nombre, precio, servicioId) {
  items.push({ nombre: nombre, precio: precio, servicioId: servicioId });
  renderItems();
  // Feedback visual: pulso en el botón del catálogo
  var btns = document.querySelectorAll('.catalogo-btn');
  btns.forEach(function(btn) {
    if (btn.querySelector('.catalogo-nombre') &&
        btn.querySelector('.catalogo-nombre').textContent.trim() === nombre) {
      btn.classList.add('catalogo-btn-added');
      setTimeout(function() { btn.classList.remove('catalogo-btn-added'); }, 400);
    }
  });
}

function quitarItem(idx) {
  var rows = document.querySelectorAll('#itemsTbody tr');
  var row = rows[idx];
  if (row) {
    row.classList.add('item-removing');
    setTimeout(function() {
      items.splice(idx, 1);
      renderItems();
    }, 220);
  } else {
    items.splice(idx, 1);
    renderItems();
  }
}

function calcularDescuento(subtotal) {
  var input = document.getElementById('descuentoValor');
  if (!input) return 0;
  var val = parseFloat(input.value) || 0;
  if (val <= 0) return 0;
  var tipo = document.querySelector('input[name="descuento_tipo"]:checked');
  if (tipo && tipo.value === 'porcentaje') {
    return Math.round(subtotal * val / 100);
  }
  return Math.min(val, subtotal);
}

function actualizarFooter() {
  var subtotal = items.reduce(function(a, b) { return a + b.precio; }, 0);
  var descuento = calcularDescuento(subtotal);
  var total = subtotal - descuento;

  var totalDisp    = document.getElementById('totalDisplay');
  var subtotalLine = document.getElementById('subtotalLine');
  var subtotalDisp = document.getElementById('subtotalDisplay');
  var descuentoDisp = document.getElementById('descuentoDisplay');

  if (totalDisp) totalDisp.textContent = '$' + total.toLocaleString('es-AR');

  if (subtotalLine) {
    if (descuento > 0) {
      subtotalLine.style.display = 'inline';
      if (subtotalDisp) subtotalDisp.textContent = '$' + subtotal.toLocaleString('es-AR');
      if (descuentoDisp) descuentoDisp.textContent = '-$' + descuento.toLocaleString('es-AR');
    } else {
      subtotalLine.style.display = 'none';
    }
  }
}

function recalcularDescuento() {
  actualizarFooter();
}

function renderItems() {
  var emptyMsg  = document.getElementById('emptyItems');
  var tabla     = document.getElementById('tablaItems');
  var tbody     = document.getElementById('itemsTbody');
  var footer    = document.getElementById('ventaFooter');

  if (!items.length) {
    emptyMsg.style.display = 'block';
    tabla.style.display = 'none';
    if (footer) footer.style.display = 'none';
    return;
  }

  emptyMsg.style.display = 'none';
  tabla.style.display = 'table';
  if (footer) footer.style.display = 'flex';

  tbody.innerHTML = '';

  items.forEach(function(item, idx) {
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td>' +
        escapeHtml(item.nombre) +
        '<input type="hidden" name="item_nombre" value="' + escapeHtml(item.nombre) + '">' +
        '<input type="hidden" name="item_servicio_id" value="' + (item.servicioId || '') + '">' +
      '</td>' +
      '<td>' +
        '<input type="number" name="item_precio" value="' + item.precio + '"' +
               ' step="1" min="0" style="width:110px"' +
               ' onchange="actualizarPrecio(' + idx + ', this.value)">' +
      '</td>' +
      '<td>' +
        '<button type="button" class="btn btn-sm btn-danger-ghost" onclick="quitarItem(' + idx + ')">✕</button>' +
      '</td>';
    tbody.appendChild(tr);
  });

  actualizarFooter();
}

function actualizarPrecio(idx, val) {
  items[idx].precio = parseFloat(val) || 0;
  actualizarFooter();
}

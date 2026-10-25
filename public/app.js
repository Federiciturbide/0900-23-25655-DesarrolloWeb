const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = { view: 'home', user: null, catalog: '', catalogRows: [], cart: [], products: [], clients: [], suppliers: [], pos: {clientId:'',payment:'Efectivo',cash:'',voucher:'',usePoints:false,customer_name:'',customer_nit:'CF',customer_address:''}, purchaseLines: [], camera: null, invoiceSearch: '' };
const titles = {home:['Operaciones diarias','Resumen'],cash:['Punto de Venta','Caja'],pos:['Punto de Venta','Despacho y cobro'],invoices:['Ventas','Facturación'],returns:['Ventas','Devoluciones'],purchases:['Compras','Compras a proveedores'],products:['Almacén','Productos y precios'],clients:['Contactos','Clientes'],suppliers:['Contactos','Proveedores'],promotions:['Configuración','Promociones'],scan:['Punto de Venta','Lectura de código QR'],reports:['Informes','Reportes']};
const labelTypes = {discount:'Descuento de producto',free_product:'Producto gratuito',gift_voucher:'Vale de regalo',half_second:'Segundo a mitad de precio',wholesale:'Precio de mayoreo',points:'Puntos por producto'};
const money = value => 'Q ' + Number(value || 0).toLocaleString('es-GT',{minimumFractionDigits:2,maximumFractionDigits:2});
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = value => Number(value || 0).toLocaleString('es-GT',{maximumFractionDigits:2});
const today = () => { const d=new Date(); return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'); };
const prettyDate = value => value ? new Date(value).toLocaleString('es-GT') : '—';

async function api(path, method='GET', data=null) {
  const options = {method,credentials:'same-origin',headers:{}};
  if (data !== null) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(data); }
  const response = await fetch(path,options);
  let result = {};
  try { result = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.');
  return result;
}
function toast(message) {
  const box = $('#toast'); box.textContent = message; box.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => box.classList.remove('show'),3500);
}
function notice(message, isError=false) {
  const box = $('#notice'); box.textContent = message; box.className = 'notice' + (isError ? ' error' : ''); box.hidden = !message;
  if (message) window.scrollTo({top:0,behavior:'smooth'});
}
function showApp(user) {
  state.user = user; $('#login-panel').hidden = true; $('#app-shell').hidden = false;
  $('#user-name').textContent = user.display_name || user.username;
  $('#today-label').textContent = new Date().toLocaleDateString('es-GT',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
  go('home');
}
function startLogin() { $('#login-panel').hidden = false; $('#app-shell').hidden = true; $('#login-username').focus(); }
async function go(view) {
  stopCamera();
  state.view = view in titles ? view : 'home';
  $$('.view').forEach(el => el.hidden = true);
  const page = $('#view-' + state.view); page.hidden = false;
  const [module,title] = titles[state.view]; $('#page-module').textContent = module; $('#page-title').textContent = title;
  $$('.module-bar button').forEach(button => button.classList.toggle('active',button.dataset.view === state.view));
  notice('');
  try {
    if (state.view === 'home') await renderHome();
    if (['clients','suppliers','products','promotions'].includes(state.view)) await renderCatalog(state.view);
    if (state.view === 'cash') await renderCash();
    if (state.view === 'pos') await renderPOS();
    if (state.view === 'invoices') await renderInvoices();
    if (state.view === 'returns') await renderReturns();
    if (state.view === 'purchases') await renderPurchases();
    if (state.view === 'reports') await renderReports();
    if (state.view === 'scan') renderScan();
  } catch (error) { notice(error.message,true); }
  history.replaceState(null,'','#' + state.view);
}
function panel(title,content,extra='') {
  return '<article class="panel"><div class="panel-title">' + title + '</div><div class="panel-body ' + extra + '">' + content + '</div></article>';
}
function stat(title,value,foot) {
  return '<div class="stat"><div class="stat-title">' + title + '</div><div class="stat-value">' + value + '</div><div class="stat-foot">' + foot + '</div></div>';
}
async function renderHome() {
  const d = await api('/api/dashboard');
  const register = d.cash_register;
  const regText = register.is_open ? 'Abierta desde ' + prettyDate(register.opened_at) + ' · Fondo ' + money(register.opening_amount) : 'No hay caja abierta';
  $('#view-home').innerHTML =
    '<div class="stats-grid">' +
    stat('Ventas de hoy',money(d.today_total),d.today_sales + ' operaciones') +
    stat('Devoluciones de hoy',d.today_returns,'Productos dañados o vencidos') +
    stat('Productos activos',d.products,d.low_stock + ' con existencia baja') +
    stat('Clientes activos',d.clients,d.suppliers + ' proveedores registrados') +
    '</div><div class="home-columns">' +
    panel('Estado de caja','<div class="status-line"><b>' + esc(regText) + '</b></div>' +
      (register.is_open ? '<p>Ventas en efectivo: ' + money(register.cash_sales) + ' · Reembolsos en efectivo: ' + money(register.cash_returns) + '</p><p>Efectivo esperado: <b>' + money(register.expected_cash) + '</b></p>' : '<p>Abre una sesión para comenzar a vender.</p>') +
      '<button class="button primary" data-view="cash">Ir a caja</button> <button class="button" data-view="pos">Abrir punto de venta</button>') +
    panel('Accesos del sistema','<div class="quick-list">' +
      '<button data-view="pos"><b>Punto de venta</b><span>Despachar, aplicar promociones y cobrar</span></button>' +
      '<button data-view="invoices"><b>Facturación</b><span>Consultar e imprimir comprobantes con QR</span></button>' +
      '<button data-view="purchases"><b>Compras</b><span>Ingresar mercadería y actualizar existencias</span></button>' +
      '<button data-view="reports"><b>Reportes</b><span>Cortes, ventas, devoluciones y compras</span></button>' +
      '<button data-view="clients"><b>Clientes</b><span>Contactos y puntos acumulados</span></button>' +
      '<button data-view="promotions"><b>Promociones</b><span>Descuentos, vales, mayoreo y puntos</span></button>' +
      '</div>') +
    '</div><div class="callout">Sistema de inventario y ventas con almacenamiento local en SQLite. La información del negocio queda registrada en la base de datos.</div>';
}

const catalogConfig = {
  clients:{endpoint:'clients',title:'Clientes',singular:'cliente',search:'Buscar por código, nombre, NIT o teléfono',columns:[['code','Código'],['name','Nombre'],['nit','NIT'],['phone','Teléfono'],['email','Correo'],['loyalty_points','Puntos'],['active','Estado']]},
  suppliers:{endpoint:'suppliers',title:'Proveedores',singular:'proveedor',search:'Buscar por código, empresa o contacto',columns:[['code','Código'],['business_name','Nombre comercial'],['contact_name','Contacto'],['nit','NIT'],['phone','Teléfono'],['active','Estado']]},
  products:{endpoint:'products',title:'Productos y precios',singular:'producto',search:'Buscar por SKU, nombre, categoría o proveedor',columns:[['sku','SKU'],['name','Producto'],['category','Categoría'],['supplier_name','Proveedor'],['stock','Existencia'],['cost','Costo'],['sale_price','Precio de venta'],['active','Estado']]},
  promotions:{endpoint:'promotions',title:'Promociones',singular:'promoción',search:'Buscar por código, nombre o categoría',columns:[['code','Código'],['name','Promoción'],['type','Tipo'],['category','Familia'],['min_qty','Mínimo'],['active','Estado']]}
};
function catalogSearchString(row,kind) { return catalogConfig[kind].columns.map(col => row[col[0]]).join(' ').toLowerCase(); }
async function renderCatalog(kind) {
  state.catalog = kind;
  const config = catalogConfig[kind];
  const rows = await api('/api/' + config.endpoint); state.catalogRows = rows;
  $('#view-' + kind).innerHTML =
    '<div class="page-actions"><div><h2>Catálogo de ' + config.title.toLowerCase() + '</h2><p>Los registros se conservan para mantener la referencia histórica.</p></div><button class="button primary" data-create="' + kind + '">+ Nuevo ' + config.singular + '</button></div>' +
    '<div class="toolbar"><span class="count" id="catalog-count">' + rows.length + ' registros</span><input type="search" id="catalog-search" placeholder="' + config.search + '"></div>' +
    '<div class="table-wrap"><table><thead><tr>' + config.columns.map(c => '<th>' + c[1] + '</th>').join('') + '<th class="actions">Acciones</th></tr></thead><tbody id="catalog-body"></tbody></table></div>';
  drawCatalogRows('');
}
function drawCatalogRows(term) {
  const kind = state.catalog, config = catalogConfig[kind];
  const matched = state.catalogRows.filter(row => catalogSearchString(row,kind).includes(term.toLowerCase()));
  $('#catalog-count').textContent = matched.length + ' de ' + state.catalogRows.length + ' registros';
  $('#catalog-body').innerHTML = matched.length ? matched.map(row => {
    const cells = config.columns.map(([key,label]) => {
      let val = row[key];
      if (key === 'active') val = row.active ? '<span class="tag green">Activo</span>' : '<span class="tag red">Inactivo</span>';
      else if (key === 'type') val = labelTypes[val] || val;
      else if (key === 'stock') val = num(val) + (Number(val) <= 5 ? ' ⚠' : '');
      else if (key === 'cost' || key === 'sale_price') val = money(val);
      return '<td>' + (key === 'active' ? val : esc(val === null || val === '' ? '—' : val)) + '</td>';
    }).join('');
    return '<tr>' + cells + '<td class="actions">' + (kind === 'products' ? '<button class="button small" data-prices="' + row.id + '" title="Historial de precios">Precios</button> ' : '') +
      '<button class="button small" data-edit="' + kind + '" data-id="' + row.id + '">Editar</button> ' +
      '<button class="button small" data-toggle="' + kind + '" data-id="' + row.id + '">' + (row.active ? 'Desactivar' : 'Reactivar') + '</button></td></tr>';
  }).join('') : '<tr><td class="empty-row" colspan="' + (config.columns.length + 1) + '">No hay registros que coincidan con la búsqueda.</td></tr>';
}
function field(name,label,value='',type='text',required=false,options=[],full=false,placeholder='') {
  const cls = 'field' + (full ? ' full' : '');
  let input = '';
  if (type === 'select') input = '<select name="' + name + '"' + (required ? ' required' : '') + '>' + (required ? '' : '<option value="">— Seleccione —</option>') + options.map(option => '<option value="' + esc(option.value) + '"' + (String(option.value) === String(value ?? '') ? ' selected' : '') + '>' + esc(option.label) + '</option>').join('') + '</select>';
  else if (type === 'textarea') input = '<textarea name="' + name + '"' + (required ? ' required' : '') + ' placeholder="' + esc(placeholder) + '">' + esc(value) + '</textarea>';
  else if (type === 'checkbox') input = '<input name="' + name + '" type="checkbox"' + (value ? ' checked' : '') + '>';
  else input = '<input name="' + name + '" type="' + type + '" value="' + esc(value ?? '') + '"' + (required ? ' required' : '') + (placeholder ? ' placeholder="' + esc(placeholder) + '"' : '') + '>';
  return '<label class="' + cls + '">' + label + input + '</label>';
}
async function openCatalogEditor(kind,id=null) {
  const config = catalogConfig[kind], row = id ? state.catalogRows.find(x => x.id === Number(id)) : {};
  const values = row || {};
  $('#dialog-title').textContent = (id ? 'Editar ' : 'Nuevo ') + config.singular;
  $('#record-form').dataset.kind = kind; $('#record-form').dataset.id = id || '';
  let html = '';
  if (kind === 'clients') {
    html += field('code','Código',values.code,'text',true)+field('name','Nombre completo',values.name,'text',true)+field('nit','NIT',values.nit)+field('phone','Teléfono',values.phone,'tel')+field('email','Correo electrónico',values.email,'email')+field('address','Dirección',values.address,'text',false,[],true);
  } else if (kind === 'suppliers') {
    html += field('code','Código',values.code,'text',true)+field('business_name','Nombre comercial',values.business_name,'text',true)+field('contact_name','Persona de contacto',values.contact_name)+field('nit','NIT',values.nit)+field('phone','Teléfono',values.phone,'tel')+field('email','Correo electrónico',values.email,'email')+field('address','Dirección',values.address,'text',false,[],true);
  } else if (kind === 'products') {
    const suppliers = await api('/api/suppliers/options');
    html += field('sku','SKU',values.sku,'text',true)+field('name','Nombre del producto',values.name,'text',true)+field('category','Familia o categoría',values.category,'text',true)+field('supplier_id','Proveedor',values.supplier_id,'select',false,suppliers.map(s=>({value:s.id,label:s.business_name})))+field('stock','Existencia',values.stock ?? 0,'number',true)+field('cost','Costo',values.cost ?? 0,'number',true)+field('sale_price','Precio de venta',values.sale_price ?? 0,'number',true)+field('description','Descripción',values.description,'textarea',false,[],true);
  } else {
    const options = await api('/api/promotion-options');
    const types = Object.entries(labelTypes).map(([value,label])=>({value,label}));
    const productOptions = options.products.map(p=>({value:p.id,label:p.sku+' · '+p.name}));
    const categoryOptions = options.categories.map(c=>({value:c,label:c}));
    html += field('code','Código',values.code,'text',true)+field('name','Nombre',values.name,'text',true)+field('type','Tipo de promoción',values.type || 'discount','select',true,types)+field('category','Familia de productos',values.category,'select',false,categoryOptions)+field('product_id','Producto específico (opcional)',values.product_id,'select',false,productOptions)+field('min_qty','Cantidad mínima',values.min_qty ?? 1,'number',true)+field('discount_percent','Descuento (%)',values.discount_percent ?? 0,'number')+field('wholesale_price','Precio unitario al mayoreo',values.wholesale_price ?? 0,'number')+field('reward_product_id','Producto de regalo',values.reward_product_id,'select',false,productOptions)+field('voucher_amount','Valor del vale (Q)',values.voucher_amount ?? 0,'number')+field('points_per_unit','Puntos por unidad',values.points_per_unit ?? 0,'number')+field('starts_at','Válida desde (opcional)',values.starts_at || '','date')+field('ends_at','Válida hasta (opcional)',values.ends_at || '','date')+field('active','Promoción activa',values.active ?? true,'checkbox');
  }
  $('#form-fields').innerHTML = html;
  $('#edit-dialog').showModal();
}

async function renderCash() {
  const r = await api('/api/cash-register');
  $('#view-cash').innerHTML = r.is_open ?
    '<div class="page-actions"><div><h2>Sesión de caja en curso</h2><p>Abierta por ' + esc(r.opened_by) + ' · ' + prettyDate(r.opened_at) + '</p></div><span class="tag green">Caja abierta</span></div>' +
    '<div class="stats-grid">' + stat('Fondo inicial',money(r.opening_amount),'Monto al abrir') + stat('Ventas en efectivo',money(r.cash_sales),'Ingresos registrados') + stat('Reembolsos en efectivo',money(r.cash_returns),'Devoluciones') + stat('Efectivo esperado',money(r.expected_cash),'Antes de contar') + '</div>' +
    panel('Cierre de caja','<form id="close-register-form" class="inline-form">' + field('counted_amount','Efectivo contado (Q)','','number',true) + '<button class="button primary">Cerrar sesión</button></form><p class="muted">Al cerrar se guarda el total esperado, el monto contado y la diferencia.</p>') :
    '<div class="page-actions"><div><h2>Apertura de caja</h2><p>Registra el fondo disponible antes de iniciar las ventas.</p></div><span class="tag red">Caja cerrada</span></div>' +
    panel('Nueva sesión','<form id="open-register-form" class="inline-form">' + field('opening_amount','Fondo inicial en efectivo (Q)','','number',true) + '<button class="button primary">Abrir caja</button></form><p class="muted">Solo puede haber una sesión de caja abierta a la vez.</p>') +
    '<div class="callout">Debes abrir caja para registrar cobros y devoluciones.</div>';
}
async function renderPOS() {
  const results = await Promise.all([api('/api/products/options'),api('/api/clients'),api('/api/cash-register')]);
  state.products = results[0]; state.clients = results[1].filter(c=>c.active); const register = results[2];
  if (!register.is_open) {
    $('#view-pos').innerHTML = '<div class="callout">La caja está cerrada. Abre una sesión antes de despachar productos.</div><button class="button primary" data-view="cash">Ir a apertura de caja</button>';
    return;
  }
  const productOptions = state.products.map(p=>'<option value="' + p.id + '">' + esc(p.sku+' · '+p.name+' — '+money(p.sale_price)+' (existencia '+num(p.stock)+')') + '</option>').join('');
  const clientOptions = '<option value="">Consumidor final</option>' + state.clients.map(c=>'<option value="' + c.id + '"' + (String(c.id)===String(state.pos.clientId)?' selected':'') + '>' + esc(c.name+' · '+c.nit+' · '+c.loyalty_points+' puntos') + '</option>').join('');
  const subtotal = state.cart.reduce((sum,line)=>sum+line.quantity*line.product.sale_price,0);
  $('#view-pos').innerHTML =
    '<div class="page-actions"><div><h2>Despacho de productos</h2><p>Agrega productos por código, revisa cantidades y registra el pago.</p></div><span class="tag green">Caja abierta</span></div>' +
    '<div class="pos-layout"><div>' +
    panel('Productos','<div class="product-pick"><select id="product-picker"><option value="">Seleccione producto / SKU</option>' + productOptions + '</select><input id="product-quantity" type="number" value="1" min="0.01" step="0.01" aria-label="Cantidad"><button class="button primary" id="add-cart">Agregar</button></div>' +
      '<div class="toolbar"><span class="count">Escanea o escribe el SKU</span><input id="sku-entry" type="search" placeholder="SKU y Enter"></div>') +
    panel('Detalle de la venta',state.cart.length ? '<div class="table-wrap"><table class="cart-table"><thead><tr><th>Producto</th><th>Existencia</th><th>Cantidad</th><th>Precio</th><th>Importe</th><th></th></tr></thead><tbody>' +
      state.cart.map((line,index)=>'<tr><td>' + esc(line.product.name) + '<br><small class="muted">' + esc(line.product.sku) + '</small></td><td>' + num(line.product.stock) + '</td><td><input data-cart-qty="' + index + '" type="number" min="0.01" step="0.01" value="' + line.quantity + '"></td><td>' + money(line.product.sale_price) + '</td><td>' + money(line.quantity*line.product.sale_price) + '</td><td><button class="button small danger" data-cart-remove="' + index + '">Quitar</button></td></tr>').join('') +
      '</tbody></table></div><div class="cart-total">Subtotal estimado: ' + money(subtotal) + '</div><p class="muted">Los descuentos, vales y puntos se aplican al confirmar la operación.</p>' :
      '<div class="empty-row">No hay productos agregados a la venta.</div>') +
    '</div><div>' +
    panel('Cliente y datos de factura','<form id="pos-form"><label class="field">Cliente registrado<select name="client_id" id="pos-client">' + clientOptions + '</select></label>' +
      '<div id="final-customer-fields"' + (state.pos.clientId ? ' hidden' : '') + ' class="form-grid" style="margin-top:9px">' +
      field('customer_name','Nombre del cliente',state.pos.customer_name,'text',false,[],false,'Consumidor final')+
      field('customer_nit','NIT',state.pos.customer_nit || 'CF')+field('customer_address','Dirección',state.pos.customer_address,'text',false,[],true)+'</div>' +
      '<div class="form-grid" style="margin-top:9px">' + field('voucher_code','Código de vale',state.pos.voucher,'text',false,[],false,'Opcional') +
      '<label class="field">Puntos disponibles<input id="points-display" value="' + (state.clients.find(c=>String(c.id)===String(state.pos.clientId))?.loyalty_points || 0) + '" readonly></label>' +
      '<label class="field full"><span><input name="use_points" type="checkbox"' + (state.pos.usePoints?' checked':'') + '> Usar puntos disponibles (1 punto = Q1)</span></label></div>' +
      '<div class="form-grid" style="margin-top:9px">' + field('payment_method','Forma de pago',state.pos.payment,'select',true,['Efectivo','Tarjeta de crédito','Tarjeta de débito'].map(x=>({value:x,label:x}))) +
      field('amount_received','Efectivo recibido (Q)',state.pos.cash || subtotal.toFixed(2),'number',false)+'</div>' +
      '<div id="pos-total-preview" class="callout">Total estimado antes de promociones: <b>' + money(subtotal) + '</b></div>' +
      '<button class="button primary wide" type="submit"' + (!state.cart.length?' disabled':'') + '>Cobrar y generar factura</button></form>') +
    '</div></div>';
  const cashField = $('#pos-form [name=amount_received]'); cashField.parentElement.hidden = state.pos.payment !== 'Efectivo';
}
async function renderInvoices(term='') {
  state.invoiceSearch = term;
  const list = await api('/api/invoices?term=' + encodeURIComponent(term));
  $('#view-invoices').innerHTML = '<div class="page-actions"><div><h2>Facturas emitidas</h2><p>Consulta el detalle de compra, las promociones y el código QR.</p></div><button class="button" data-view="pos">Nueva venta</button></div>' +
    '<div class="toolbar"><span class="count">' + list.length + ' facturas</span><form id="invoice-search-form" class="action-group"><input type="search" name="term" value="' + esc(term) + '" placeholder="Factura, venta o cliente"><button class="button">Buscar</button></form></div>' +
    '<div class="table-wrap"><table><thead><tr><th>Factura</th><th>Fecha</th><th>Cliente</th><th>NIT</th><th>Total</th><th>Pago</th><th></th></tr></thead><tbody>' +
    (list.length ? list.map(row=>'<tr><td><b>' + esc(row.invoice_number) + '</b></td><td>' + prettyDate(row.issued_at) + '</td><td>' + esc(row.customer_name) + '</td><td>' + esc(row.customer_nit) + '</td><td>' + money(row.total) + '</td><td>' + esc(row.payment_method) + '</td><td class="actions"><button class="button small" data-open-invoice="' + esc(row.invoice_number) + '">Ver / imprimir</button></td></tr>').join('') : '<tr><td class="empty-row" colspan="7">Todavía no hay facturas registradas.</td></tr>') +
    '</tbody></table></div>';
}
function qrSvg(matrix) {
  const size = matrix.length, pixels = [];
  for (let y=0;y<size;y++) for (let x=0;x<size;x++) if(matrix[y][x]) pixels.push('<rect x="' + (x+4) + '" y="' + (y+4) + '" width="1" height="1"/>');
  return '<svg class="qr-code" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + (size+8) + ' ' + (size+8) + '" shape-rendering="crispEdges" role="img" aria-label="Código QR"><rect width="100%" height="100%" fill="white"/><g fill="#111">' + pixels.join('') + '</g></svg>';
}
function invoiceMarkup(inv) {
  const qr = qrSvg(inv.qr_matrix || []);
  return '<article class="invoice-paper"><div class="invoice-head"><div><h2>La casa del rincón guatemalteco</h2><div>Comprobante de venta</div></div><div class="invoice-meta"><b>' + esc(inv.invoice_number) + '</b><br>' + prettyDate(inv.issued_at) + '</div></div>' +
    '<div class="invoice-customer"><div><b>Cliente:</b> ' + esc(inv.customer_name) + '</div><div><b>NIT:</b> ' + esc(inv.customer_nit || 'CF') + '</div><div><b>Dirección:</b> ' + esc(inv.customer_address || '—') + '</div><div><b>Atendió:</b> ' + esc(inv.cashier) + '</div></div>' +
    '<div class="table-wrap"><table class="invoice-table"><thead><tr><th>SKU</th><th>Descripción</th><th>Cantidad</th><th>Precio unitario</th><th>Descuento</th><th>Total</th></tr></thead><tbody>' + inv.lines.map(l=>'<tr><td>' + esc(l.sku) + '</td><td>' + esc(l.product_name) + (l.is_free ? ' <span class="tag orange">Gratis</span>' : '') + '</td><td>' + num(l.quantity) + '</td><td>' + money(l.unit_price) + '</td><td>' + money(l.discount_amount) + '</td><td>' + money(l.line_total) + '</td></tr>').join('') + '</tbody></table></div>' +
    '<div class="invoice-totals"><div><span>Subtotal</span><b>' + money(inv.subtotal) + '</b></div><div><span>Descuentos</span><b>− ' + money(inv.discount_total) + '</b></div><div class="grand"><span>Total</span><b>' + money(inv.total) + '</b></div><div><span>Forma de pago</span><b>' + esc(inv.payment_method) + '</b></div>' + (inv.payment_method==='Efectivo'?'<div><span>Efectivo recibido</span><b>' + money(inv.amount_received) + '</b></div><div><span>Cambio</span><b>' + money(inv.change_due) + '</b></div>':'') + '</div>' +
    '<div class="invoice-bottom"><div><b>Promociones:</b> ' + esc(inv.promotion_text || 'Sin promoción') + (inv.issued_voucher ? '<br><b>Vale generado:</b> ' + esc(inv.issued_voucher.code) + ' (' + money(inv.issued_voucher.amount) + ')' : '') + '<br><small>Escanea para consultar la promoción vinculada.</small></div>' + qr + '</div></article>';
}
async function openInvoice(key) {
  const inv = await api('/api/invoices/' + encodeURIComponent(key));
  $('#invoice-content').innerHTML = invoiceMarkup(inv); $('#invoice-dialog').showModal();
}
async function renderReturns() {
  const [invoices,rows] = await Promise.all([api('/api/invoices'),api('/api/returns')]);
  $('#view-returns').innerHTML = '<div class="page-actions"><div><h2>Devoluciones</h2><p>Registra únicamente producto dañado o vencido y selecciona el medio de reembolso.</p></div></div>' +
    panel('Registrar devolución','<form id="return-form"><div class="form-grid">' +
      '<label class="field full">Factura<select id="return-invoice" required><option value="">Seleccione factura</option>' + invoices.map(i=>'<option value="' + esc(i.invoice_number) + '">' + esc(i.invoice_number+' · '+i.customer_name+' · '+money(i.total)) + '</option>').join('') + '</select></label>' +
      '<label class="field full">Producto y línea<select id="return-line" name="sale_line_id" required><option value="">Seleccione una factura primero</option></select></label>' +
      field('quantity','Cantidad a devolver','','number',true)+field('reason','Motivo','Daño','select',true,[{value:'Daño',label:'Producto dañado'},{value:'Vencimiento',label:'Producto vencido'}])+
      field('payment_method','Medio de reembolso','Efectivo','select',true,['Efectivo','Tarjeta de crédito','Tarjeta de débito'].map(x=>({value:x,label:x})))+
      '</div><div class="callout">El producto devuelto no vuelve al inventario porque se reporta como dañado o vencido. La devolución queda asociada a su factura.</div><button class="button primary">Guardar devolución</button></form>') +
    panel('Devoluciones registradas','<div class="table-wrap"><table><thead><tr><th>Número</th><th>Fecha</th><th>Factura</th><th>Cliente</th><th>Producto</th><th>Cantidad</th><th>Motivo</th><th>Reembolso</th></tr></thead><tbody>' +
      (rows.length?rows.map(r=>'<tr><td>' + esc(r.number) + '</td><td>' + prettyDate(r.created_at) + '</td><td>' + esc(r.invoice_number) + '</td><td>' + esc(r.customer_name) + '</td><td>' + esc(r.product_name) + '</td><td>' + num(r.quantity) + '</td><td>' + esc(r.reason) + '</td><td>' + money(r.refund_amount) + '</td></tr>').join(''):'<tr><td colspan="8" class="empty-row">No hay devoluciones registradas.</td></tr>') + '</tbody></table></div>');
}
async function loadReturnLines(invoiceNo) {
  const select = $('#return-line');
  if (!invoiceNo) { select.innerHTML='<option value="">Seleccione una factura primero</option>'; return; }
  const inv = await api('/api/invoices/' + encodeURIComponent(invoiceNo));
  select.innerHTML='<option value="">Seleccione producto</option>' + inv.lines.map(line=>{
    const returned=Number(line.returned_quantity||0), remaining=Math.max(0,Number(line.quantity)-returned);
    return '<option value="' + line.id + '" data-remaining="' + remaining + '" data-unit="' + Number(line.line_total)/Number(line.quantity) + '"' + (remaining===0?' disabled':'') + '>' + esc(line.sku+' · '+line.product_name+' — disponible para devolver: '+num(remaining)) + '</option>';
  }).join('');
}
async function renderPurchases() {
  const [suppliers,products,purchases] = await Promise.all([api('/api/suppliers/options'),api('/api/products/options'),api('/api/purchases')]);
  state.suppliers = suppliers; state.products = products;
  $('#view-purchases').innerHTML = '<div class="page-actions"><div><h2>Ingreso de mercadería</h2><p>La compra aumenta el inventario y registra los costos del proveedor.</p></div></div>' +
    panel('Nueva compra','<form id="purchase-form"><div class="form-grid"><label class="field">Proveedor<select name="supplier_id" required><option value="">Seleccione proveedor</option>' + suppliers.map(s=>'<option value="' + s.id + '">' + esc(s.business_name) + '</option>').join('') + '</select></label><div></div></div><div id="purchase-lines" style="margin-top:12px"></div><div class="action-group"><button type="button" class="button" id="add-purchase-line">+ Agregar producto</button><button class="button primary">Registrar compra</button></div></form>') +
    panel('Compras registradas','<div class="table-wrap"><table><thead><tr><th>Número</th><th>Fecha</th><th>Proveedor</th><th>Registró</th><th>Total</th></tr></thead><tbody>' +
      (purchases.length?purchases.map(p=>'<tr><td>' + esc(p.number) + '</td><td>' + prettyDate(p.created_at) + '</td><td>' + esc(p.supplier_name) + '</td><td>' + esc(p.user_name) + '</td><td>' + money(p.total) + '</td></tr>').join(''):'<tr><td colspan="5" class="empty-row">No hay compras registradas.</td></tr>') + '</tbody></table></div>');
  state.purchaseLines=[]; addPurchaseLine();
}
function addPurchaseLine() {
  const wrap=$('#purchase-lines'); if(!wrap)return;
  const id=state.purchaseLines.length; state.purchaseLines.push({product_id:'',quantity:1,unit_cost:''});
  const opts=state.products.map(p=>'<option value="' + p.id + '">' + esc(p.sku+' · '+p.name+' (existencia '+num(p.stock)+')') + '</option>').join('');
  wrap.insertAdjacentHTML('beforeend','<div class="purchase-line" data-purchase-row="' + id + '"><label class="field">Producto<select data-purchase-product="' + id + '" required><option value="">Seleccione</option>' + opts + '</select></label><label class="field">Cantidad<input data-purchase-qty="' + id + '" type="number" min="0.01" step="0.01" value="1" required></label><label class="field">Costo unitario<input data-purchase-cost="' + id + '" type="number" min="0" step="0.01" value="0" required></label><button type="button" class="button small danger" data-purchase-remove="' + id + '">×</button></div>');
}
async function renderReports() {
  $('#view-reports').innerHTML = '<div class="page-actions"><div><h2>Informes del negocio</h2><p>Consulta cierre de caja, ventas, devoluciones, clientes y compras.</p></div></div>' +
    panel('Periodo del informe','<form id="report-form" class="report-filters">' + field('from','Desde',today(),'date',true)+field('to','Hasta',today(),'date',true)+'<button class="button primary">Consultar</button></form>') +
    '<div id="report-results"></div>';
  await loadReport(today(),today());
}
async function loadReport(start,end) {
  const r=await api('/api/reports?from='+encodeURIComponent(start)+'&to='+encodeURIComponent(end));
  $('#report-results').innerHTML='<div class="report-summary">' +
    '<div class="report-box"><small>Ventas</small><b>' + money(r.sales_total) + '</b><small>' + r.sales_count + ' facturas</small></div>' +
    '<div class="report-box"><small>Devoluciones</small><b>' + money(r.return_total) + '</b><small>' + r.return_count + ' registros</small></div>' +
    '<div class="report-box"><small>Ingreso neto</small><b>' + money(r.net_total) + '</b><small>Ventas menos devoluciones</small></div>' +
    '<div class="report-box"><small>Compras recibidas</small><b>' + money(r.purchase_total) + '</b><small>En el periodo consultado</small></div></div>' +
    panel('Ventas por forma de pago','<div class="table-wrap"><table><thead><tr><th>Forma de pago</th><th>Operaciones</th><th>Total cobrado</th></tr></thead><tbody>'+(r.sales.length?r.sales.map(s=>'<tr><td>'+esc(s.payment_method)+'</td><td>'+s.transactions+'</td><td>'+money(s.total)+'</td></tr>').join(''):'<tr><td colspan="3" class="empty-row">Sin ventas en el periodo.</td></tr>')+'</tbody></table></div>') +
    panel('Cortes y cierres de caja','<div class="table-wrap"><table><thead><tr><th>Apertura</th><th>Cierre</th><th>Encargado</th><th>Fondo inicial</th><th>Efectivo esperado</th><th>Efectivo contado</th><th>Diferencia</th></tr></thead><tbody>'+(r.cash_closings.length?r.cash_closings.map(c=>'<tr><td>'+prettyDate(c.opened_at)+'</td><td>'+prettyDate(c.closed_at)+'</td><td>'+esc(c.opened_by)+'</td><td>'+money(c.opening_amount)+'</td><td>'+(c.expected_cash===null?'—':money(c.expected_cash))+'</td><td>'+(c.counted_amount===null?'—':money(c.counted_amount))+'</td><td>'+(c.difference===null?'—':money(c.difference))+'</td></tr>').join(''):'<tr><td colspan="7" class="empty-row">No hay sesiones de caja en este periodo.</td></tr>')+'</tbody></table></div>') +
    panel('Devoluciones','<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Devolución</th><th>Factura</th><th>Cliente</th><th>Producto</th><th>Motivo</th><th>Reembolso</th></tr></thead><tbody>'+(r.returns.length?r.returns.map(x=>'<tr><td>'+prettyDate(x.created_at)+'</td><td>'+esc(x.number)+'</td><td>'+esc(x.invoice_number)+'</td><td>'+esc(x.customer_name)+'</td><td>'+esc(x.product_name)+'</td><td>'+esc(x.reason)+'</td><td>'+money(x.refund_amount)+'</td></tr>').join(''):'<tr><td colspan="7" class="empty-row">Sin devoluciones.</td></tr>')+'</tbody></table></div>') +
    panel('Reporte de clientes','<div class="table-wrap"><table><thead><tr><th>Código</th><th>Cliente</th><th>NIT</th><th>Compras</th><th>Total comprado</th><th>Puntos</th></tr></thead><tbody>'+r.clients.map(c=>'<tr><td>'+esc(c.code)+'</td><td>'+esc(c.name)+'</td><td>'+esc(c.nit)+'</td><td>'+c.purchases+'</td><td>'+money(c.total)+'</td><td>'+c.loyalty_points+'</td></tr>').join('')+'</tbody></table></div>') +
    panel('Compras de productos para existencia','<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Compra</th><th>Proveedor</th><th>SKU</th><th>Producto</th><th>Cantidad</th><th>Costo</th><th>Importe</th></tr></thead><tbody>'+(r.purchases.length?r.purchases.map(p=>'<tr><td>'+prettyDate(p.created_at)+'</td><td>'+esc(p.number)+'</td><td>'+esc(p.supplier_name)+'</td><td>'+esc(p.sku)+'</td><td>'+esc(p.product_name)+'</td><td>'+num(p.quantity)+'</td><td>'+money(p.unit_cost)+'</td><td>'+money(p.line_total)+'</td></tr>').join(''):'<tr><td colspan="8" class="empty-row">Sin compras en el periodo.</td></tr>')+'</tbody></table></div>');
}
function renderScan() {
  $('#view-scan').innerHTML='<div class="page-actions"><div><h2>Lectura de código QR</h2><p>Lee el QR impreso en una factura para conocer qué promoción se aplicó.</p></div></div>' +
    panel('Consultar promoción','<form id="scan-form" class="inline-form">' + field('payload','Contenido del QR','','text',true) + '<button class="button primary">Consultar</button></form><div id="scan-result" class="callout" hidden></div>') +
    panel('Usar cámara','<div class="camera-wrap"><button class="button" id="start-camera">Iniciar cámara</button> <button class="button" id="stop-camera" disabled>Detener cámara</button><video id="camera-video" playsinline muted></video><p id="camera-note" class="muted">La lectura con cámara requiere un navegador compatible y autorización para usarla.</p></div>');
}
async function lookupQR(payload) {
  const result=await api('/api/qr/lookup?payload='+encodeURIComponent(payload));
  const box=$('#scan-result'); box.hidden=false;
  box.className='callout'+(result.found?'':' notice error');
  box.innerHTML=result.found ? '<b>Factura:</b> '+esc(result.invoice_number)+'<br><b>Cliente:</b> '+esc(result.customer)+'<br><b>Promoción aplicada:</b> '+esc(result.promotion)+'<br><b>Tipo indicado en QR:</b> '+esc(labelTypes[result.promo_type]||result.promo_type)+'<br><button class="button small" data-open-invoice="'+esc(result.invoice_number)+'">Abrir factura</button>' : esc(result.message);
}
function stopCamera() {
  if(state.camera){state.camera.getTracks().forEach(track=>track.stop());state.camera=null;}
  const video=$('#camera-video'); if(video){video.pause();video.srcObject=null;}
  const start=$('#start-camera'),stop=$('#stop-camera'); if(start)start.disabled=false;if(stop)stop.disabled=true;
}
async function startCamera() {
  if(!('BarcodeDetector' in window)){toast('Este navegador no incluye lectura QR por cámara. Usa el campo manual o la cámara del teléfono.');return;}
  try{
    state.camera=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'},audio:false});
    const video=$('#camera-video'); video.srcObject=state.camera; await video.play();
    $('#start-camera').disabled=true; $('#stop-camera').disabled=false; $('#camera-note').textContent='Apunta la cámara al código QR de una factura.';
    const detector=new BarcodeDetector({formats:['qr_code']});
    const scan=async()=>{if(!state.camera)return;try{const codes=await detector.detect(video);if(codes.length){stopCamera();$('#scan-form [name=payload]').value=codes[0].rawValue;await lookupQR(codes[0].rawValue);return;}}catch(_){}requestAnimationFrame(scan);};
    scan();
  }catch(error){toast('No se pudo abrir la cámara: '+error.message);}
}

$('#login-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('#login-error').hidden=true;
  try{const result=await api('/api/login','POST',{username:$('#login-username').value,password:$('#login-password').value});showApp(result.user);}
  catch(error){$('#login-error').textContent=error.message;$('#login-error').hidden=false;}
});
$('#logout-button').addEventListener('click',async()=>{try{await api('/api/logout','POST',{});}catch(_){}state.user=null;state.cart=[];startLogin();});
document.addEventListener('click',async event=>{
  const viewButton=event.target.closest('[data-view]'); if(viewButton){event.preventDefault();go(viewButton.dataset.view);return;}
  const create=event.target.closest('[data-create]'); if(create){try{await openCatalogEditor(create.dataset.create);}catch(err){notice(err.message,true);}return;}
  const edit=event.target.closest('[data-edit]'); if(edit){try{state.catalog=edit.dataset.edit;await openCatalogEditor(edit.dataset.edit,edit.dataset.id);}catch(err){notice(err.message,true);}return;}
  const toggle=event.target.closest('[data-toggle]'); if(toggle){try{await api('/api/'+toggle.dataset.toggle+'/'+toggle.dataset.id,'DELETE');toast('Estado del registro actualizado.');await renderCatalog(toggle.dataset.toggle);}catch(err){notice(err.message,true);}return;}
  const price=event.target.closest('[data-prices]'); if(price){try{const rows=await api('/api/products/'+price.dataset.prices+'/prices');const p=state.catalogRows.find(x=>x.id===Number(price.dataset.prices));$('#dialog-title').textContent='Historial de precios · '+p.name;$('#form-fields').innerHTML='<div class="field full"><div class="table-wrap"><table><thead><tr><th>Vigente desde</th><th>Vigente hasta</th><th>Costo</th><th>Precio de venta</th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+prettyDate(r.effective_from)+'</td><td>'+prettyDate(r.effective_to)+'</td><td>'+money(r.cost)+'</td><td>'+money(r.sale_price)+'</td></tr>').join('')+'</tbody></table></div></div>';$('#record-form').dataset.kind='';$('#edit-dialog').showModal();}catch(err){notice(err.message,true);}return;}
  const remove=event.target.closest('[data-cart-remove]'); if(remove){state.cart.splice(Number(remove.dataset.cartRemove),1);renderPOS();return;}
  const add=event.target.closest('#add-cart'); if(add){const id=Number($('#product-picker').value),qty=Number($('#product-quantity').value);const product=state.products.find(p=>p.id===id);if(!product||qty<=0){toast('Selecciona un producto y una cantidad válida.');return;}const existing=state.cart.find(x=>x.product.id===id);if(existing)existing.quantity+=qty;else state.cart.push({product,quantity:qty});renderPOS();return;}
  const inv=event.target.closest('[data-open-invoice]');if(inv){try{await openInvoice(inv.dataset.openInvoice);}catch(err){notice(err.message,true);}return;}
  if(event.target.closest('[data-close-dialog]')){$('#edit-dialog').close();return;}
  if(event.target.closest('[data-close-invoice]')){$('#invoice-dialog').close();return;}
  if(event.target.closest('#print-invoice')){window.print();return;}
  if(event.target.closest('#add-purchase-line')){addPurchaseLine();return;}
  const removePurchase=event.target.closest('[data-purchase-remove]');if(removePurchase){const row=removePurchase.closest('[data-purchase-row]');row.remove();return;}
  if(event.target.closest('#start-camera')){await startCamera();return;}
  if(event.target.closest('#stop-camera')){stopCamera();return;}
});
document.addEventListener('input',event=>{
  if(event.target.id==='catalog-search')drawCatalogRows(event.target.value);
  if(event.target.matches('[data-cart-qty]')){const index=Number(event.target.dataset.cartQty),qty=Number(event.target.value);if(qty>0&&state.cart[index]){state.cart[index].quantity=qty;const row=event.target.closest('tr');row.children[4].textContent=money(qty*state.cart[index].product.sale_price);const subtotal=state.cart.reduce((s,x)=>s+x.quantity*x.product.sale_price,0);$('.cart-total').textContent='Subtotal estimado: '+money(subtotal);$('#pos-total-preview').innerHTML='Total estimado antes de promociones: <b>'+money(subtotal)+'</b>';const cash=$('#pos-form [name=amount_received]');if(cash&&state.pos.payment==='Efectivo'&&!cash.dataset.touched)cash.value=subtotal.toFixed(2);}}
});
document.addEventListener('change',event=>{
  if(event.target.id==='pos-client'){state.pos.clientId=event.target.value;const client=state.clients.find(c=>String(c.id)===String(event.target.value));$('#final-customer-fields').hidden=!!client;$('#points-display').value=client?client.loyalty_points:0;return;}
  if(event.target.name==='payment_method'){state.pos.payment=event.target.value;$('#pos-form [name=amount_received]').parentElement.hidden=event.target.value!=='Efectivo';return;}
  if(event.target.name==='use_points'){state.pos.usePoints=event.target.checked;return;}
  if(event.target.matches('[data-purchase-product]')){const id=Number(event.target.value);const p=state.products.find(x=>x.id===id);const cost=$('[data-purchase-cost="'+event.target.dataset.purchaseProduct+'"]');if(p&&cost)cost.value=Number(p.cost||0).toFixed(2);}
  if(event.target.id==='return-invoice')loadReturnLines(event.target.value).catch(err=>notice(err.message,true));
});
$('#record-form').addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget,kind=form.dataset.kind,id=form.dataset.id;if(!kind)return;
  const payload=Object.fromEntries(new FormData(form).entries());
  if(kind==='promotions')payload.active=$('[name=active]',form).checked;
  if(kind==='products'){payload.stock=Number(payload.stock);payload.cost=Number(payload.cost);payload.sale_price=Number(payload.sale_price);}
  try{await api('/api/'+kind+(id?'/'+id:''),id?'PUT':'POST',payload);$('#edit-dialog').close();toast('Registro guardado.');await renderCatalog(kind);}catch(err){notice(err.message,true);}
});
document.addEventListener('submit',async event=>{
  const form=event.target;
  if(form.id==='open-register-form'){event.preventDefault();try{await api('/api/cash-register/open','POST',{opening_amount:Number(new FormData(form).get('opening_amount'))});toast('Caja abierta.');await go('cash');}catch(err){notice(err.message,true);}return;}
  if(form.id==='close-register-form'){event.preventDefault();try{const result=await api('/api/cash-register/close','POST',{counted_amount:Number(new FormData(form).get('counted_amount'))});toast('Caja cerrada. Diferencia: '+money(result.difference));await go('cash');}catch(err){notice(err.message,true);}return;}
  if(form.id==='pos-form'){event.preventDefault();if(!state.cart.length){toast('Agrega al menos un producto.');return;}
    const data=Object.fromEntries(new FormData(form).entries());data.client_id=data.client_id||null;data.use_points=$('[name=use_points]',form).checked;data.lines=state.cart.map(x=>({product_id:x.product.id,quantity:x.quantity}));
    data.amount_received=Number(data.amount_received||0);
    try{const invoice=await api('/api/sales','POST',data);state.cart=[];state.pos={clientId:'',payment:'Efectivo',cash:'',voucher:'',usePoints:false,customer_name:'',customer_nit:'CF',customer_address:''};await renderPOS();$('#invoice-content').innerHTML=invoiceMarkup(invoice);$('#invoice-dialog').showModal();toast('Venta registrada: '+invoice.invoice_number);}catch(err){notice(err.message,true);}return;
  }
  if(form.id==='invoice-search-form'){event.preventDefault();await renderInvoices(new FormData(form).get('term')||'');return;}
  if(form.id==='return-form'){event.preventDefault();const data=Object.fromEntries(new FormData(form).entries());data.quantity=Number(data.quantity);try{const result=await api('/api/returns','POST',data);toast('Devolución '+result.number+' registrada por '+money(result.refund_amount));await renderReturns();}catch(err){notice(err.message,true);}return;}
  if(form.id==='purchase-form'){event.preventDefault();const lines=$$('[data-purchase-row]').map(row=>({product_id:Number($('[data-purchase-product]',row).value),quantity:Number($('[data-purchase-qty]',row).value),unit_cost:Number($('[data-purchase-cost]',row).value)})).filter(x=>x.product_id);const data={supplier_id:Number(new FormData(form).get('supplier_id')),lines};try{const result=await api('/api/purchases','POST',data);toast('Compra '+result.number+' registrada.');await renderPurchases();}catch(err){notice(err.message,true);}return;}
  if(form.id==='report-form'){event.preventDefault();const data=Object.fromEntries(new FormData(form).entries());try{await loadReport(data.from,data.to);}catch(err){notice(err.message,true);}return;}
  if(form.id==='scan-form'){event.preventDefault();try{await lookupQR(new FormData(form).get('payload'));}catch(err){notice(err.message,true);}return;}
});
$('#invoice-dialog').addEventListener('click',event=>{if(event.target===$('#invoice-dialog'))$('#invoice-dialog').close();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')stopCamera();if(event.key==='Enter'&&event.target.id==='sku-entry'){event.preventDefault();const sku=event.target.value.trim().toLowerCase();const product=state.products.find(p=>p.sku.toLowerCase()===sku);if(product){const row=state.cart.find(x=>x.product.id===product.id);if(row)row.quantity+=1;else state.cart.push({product,quantity:1});renderPOS();}else toast('No se encontró ese SKU.');}});
document.addEventListener('DOMContentLoaded',async()=>{
  try{const session=await api('/api/session');if(session.authenticated)showApp(session.user);else startLogin();}
  catch(_){startLogin();}
});

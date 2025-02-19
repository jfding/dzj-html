// 更新批次
$('.operation .bat-batch').click(function () {
  var ids = $.map($('table tbody :checked'), (item) => $(item).parent().parent().attr('id'));
  if (!ids.length)
    return showWarning('请选择', '当前没有选中任何记录。');
  Swal2.fire({title: '请输入批次', input: 'text', showLoaderOnConfirm: true}).then((result) => {
    if (result.value) {
      postApi('/task/batch', {data: {_ids: ids, batch: result.value}}, () => location.reload());
    }
  });
});
// 统计检索结果
$('.operation .btn-statistic a').click(function () {
  var collection = location.pathname.indexOf('page') > -1 ? 'page' : 'char';
  location.href = '/' + collection + '/task/statistic?kind=' + $(this).attr('title') + location.search.replace('?', '&');
});
// 显示退回理由、失败理由等
$('.sty-table td.return_reason').click(function () {
  if ($(this).text().length) {
    showTips($(this).text());
  }
});
// 查看页面
$('.sty-table td.doc_id').click(function () {
  if ($(this).text().length) {
    location.href = '/page/browse/' + $(this).text() + '?from=' + encodeFrom();
  }
});
// 浏览任务
$('.sty-table .action .btn-nav').click(function () {
  var node = $(this).parent().parent();
  var taskType = node.find('.task_type').attr('title');
  location.href = '/task/browse/' + taskType + '/' + node.attr('id') + '?from=' + encodeFrom();
});
// 任务详情
$('.sty-table .action .btn-detail').click(function () {
  var node = $(this).parent().parent();
  location.href = '/task/info/' + node.attr('id');
});
// 任务历程
$('.sty-table .action .btn-history').click(function () {
  var node = $(this).parent().parent();
  location.href = '/page/task/resume/' + node.find('.doc_id').text();
});
// 重新发布任务
$('.sty-table .action .btn-republish').click(function () {
  var node = $(this).parent().parent();
  var regex = /(picked|failed)/i;
  if (!node.find('.status').attr('title').match(regex)) {
    return showWarning('状态有误', '只能重新发布进行中或已失败的任务！');
  }
  showConfirm("确定重新发布吗？", "任务" + node.find('.doc_id').text().trim() + "将被重新发布！", function () {
    postApi('/task/republish/' + node.attr('id'), {data: {}}, function () {
      window.location.reload();
    });
  });
});
// 删除任务
$('.sty-table .action .btn-delete').click(function () {
  var node = $(this).parent().parent();
  var regex = /(published|fetched|pending|returned)/i;
  if (!node.find('.status').attr('title').match(regex)) {
    return showWarning('状态有误', '只能删除已发布未领取、已获取、等待前置任务及已退回的任务！');
  }
  var id = node.attr('id');
  var data = getData(id);
  var name = 'name' in data ? data.name : '';
  showConfirm("确定删除" + name + "吗？", "删除后无法恢复！", function () {
    postApi('/task/delete', {data: {_id: data._id}}, function (res) {
      showSuccess('成功', '数据' + name + '已删除');
      refresh(1000);
    }, function (err) {
      showError('删除失败', err.message);
    });
  });
});

/*---指派任务---*/
var $assignModal = $('#assignModal');
var $assignResultModal = $('#assignResultModal');
$assignModal.find(".select-user").select2({
  dropdownParent: $assignModal,
  ajax: {
    type: 'POST', url: '/api/user/list', dataType: 'json', delay: 1000, language: 'zh-CN',
    allowClear: true, width: "100%", placeholder: "请选择", maximumSelectionLength: 2,
    data: function (params) {
      return {'q': params.term, 'page': params.page || 1};
    },
    processResults: function (res) {
      return res.data;
    }
  }
});
$assignModal.find('.modal-confirm').click(function () {
  if (!$('.sty-table :checked').length) {
    $assignModal.modal('hide');
    return showError('请选择任务');
  }
  var tasks = $.map($('table tbody :checked'), function (item) {
    var node = $(item).parent().parent();
    return [[node.attr('id'), node.find('.task_type').attr('title'), node.find('.doc_id').text()]];
  });
  var data = {'tasks': tasks, 'user_id': $assignModal.find(".select-user").val()};
  postApi('/task/assign', {'data': data}, function (res) {
    var html = $.map(res.data, function (value, key) {
      return '<tr><td class="' + key + '">' + l10n[key] + '(' + value.length + ')' + '<td>' + value + '</td>' + '</td></tr>';
    }).join('');
    $assignModal.modal('hide');
    $assignResultModal.find('table').html(html);
    $assignResultModal.modal();
  });
});
$assignResultModal.find('.modal-confirm').click(function () {
  location.reload();
});


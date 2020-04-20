#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from bson import json_util
from .char import Char
from .base import CharHandler
from controller import helper as h
from controller import errors as e
from controller import validate as v


class CharTaskAdminHandler(CharHandler):
    URL = '/char/task/admin'

    page_title = '字任务管理'
    search_tips = '请搜索字种、批次号或备注'
    search_fields = ['params.ocr_txt', 'params.txt', 'batch', 'remark']
    table_fields = [
        {'id': '_id', 'name': '主键'},
        {'id': 'batch', 'name': '批次号'},
        {'id': 'task_type', 'name': '类型', 'filter': CharHandler.task_names('char')},
        {'id': 'num', 'name': '校次'},
        {'id': 'txt_kind', 'name': '字种'},
        {'id': 'char_count', 'name': '单字数量'},
        {'id': 'status', 'name': '状态', 'filter': CharHandler.task_statuses},
        {'id': 'priority', 'name': '优先级', 'filter': CharHandler.priorities},
        {'id': 'params', 'name': '输入参数'},
        {'id': 'return_reason', 'name': '退回理由'},
        {'id': 'create_time', 'name': '创建时间'},
        {'id': 'updated_time', 'name': '更新时间'},
        {'id': 'publish_time', 'name': '发布时间'},
        {'id': 'publish_by', 'name': '发布人'},
        {'id': 'picked_time', 'name': '领取时间'},
        {'id': 'picked_by', 'name': '领取人'},
        {'id': 'finished_time', 'name': '完成时间'},
        {'id': 'remark', 'name': '备注'},
    ]
    operations = [
        {'operation': 'bat-remove', 'label': '批量删除', 'title': '/task/delete'},
        {'operation': 'bat-assign', 'label': '批量指派', 'data-target': 'assignModal'},
        {'operation': 'bat-batch', 'label': '更新批次'},
        {'operation': 'btn-search', 'label': '综合检索', 'data-target': 'searchModal'},
        {'operation': 'btn-statistic', 'label': '结果统计', 'groups': [
            {'operation': 'picked_user_id', 'label': '按用户'},
            {'operation': 'task_type', 'label': '按类型'},
            {'operation': 'status', 'label': '按状态'},
        ]},
    ]
    actions = [
        {'action': 'btn-nav', 'label': '浏览'},
        {'action': 'btn-detail', 'label': '详情'},
        {'action': 'btn-delete', 'label': '删除'},
        {'action': 'btn-republish', 'label': '重新发布', 'disabled': lambda d: d['status'] not in ['picked', 'failed']},
    ]
    hide_fields = ['_id', 'params', 'return_reason', 'create_time', 'updated_time', 'publish_by']
    update_fields = []

    def format_value(self, value, key=None, doc=None):
        """ 格式化page表的字段输出"""
        if key == 'txt_kind' and value:
            return (value[:5] + '...') if len(value) > 5 else value
        return super().format_value(value, key, doc)

    def get(self):
        """ 任务管理-字任务管理"""
        try:
            # 模板参数
            kwargs = self.get_template_kwargs()
            key = re.sub(r'[\-/]', '_', self.request.path.strip('/'))
            hide_fields = json_util.loads(self.get_secure_cookie(key) or '[]')
            kwargs['hide_fields'] = hide_fields if hide_fields else kwargs['hide_fields']
            condition, params = self.get_task_search_condition(self.request.query, 'char')
            docs, pager, q, order = self.find_by_page(self, condition, self.search_fields, '-_id')
            self.render(
                'char_task_admin.html', docs=docs, pager=pager, order=order, q=q, params=params,
                format_value=self.format_value, **kwargs,
            )
        except Exception as error:
            return self.send_db_error(error)


class CharTaskStatHandler(CharHandler):
    URL = '/char/task/statistic'

    def get(self):
        """ 根据用户、任务类型或任务状态统计页任务"""
        try:
            kind = self.get_query_argument('kind', '')
            if kind not in ['picked_user_id', 'task_type', 'status']:
                return self.send_error_response(e.statistic_type_error, message='只能按用户、任务类型或任务状态统计')

            counts = list(self.db.task.aggregate([
                {'$match': self.get_task_search_condition(self.request.query, 'char')[0]},
                {'$group': {'_id': '$%s' % kind, 'count': {'$sum': 1}}},
            ]))

            trans = {}
            if kind == 'picked_user_id':
                users = list(self.db.user.find({'_id': {'$in': [c['_id'] for c in counts]}}))
                trans = {u['_id']: u['name'] for u in users}
            elif kind == 'task_type':
                trans = self.task_names()
            elif kind == 'status':
                trans = self.task_statuses
            label = dict(picked_user_id='用户', task_type='任务类型', status='任务状态')[kind]

            self.render('task_statistic.html', counts=counts, kind=kind, label=label, trans=trans)

        except Exception as error:
            return self.send_db_error(error)


class CharTaskClusterHandler(CharHandler):
    URL = ['/task/(cluster_proof|cluster_review)/@task_id',
           '/task/do/(cluster_proof|cluster_review)/@task_id',
           '/task/browse/(cluster_proof|cluster_review)/@task_id',
           '/task/update/(cluster_proof|cluster_review)/@task_id']

    page_size = 50
    txt_types = {'': '没问题', 'M': '模糊或残损', 'N': '不确定', '*': '不认识'}

    def get(self, task_type, task_id):
        """ 聚类校对页面"""
        try:
            params = self.task['params']
            ocr_txts = [c['ocr_txt'] for c in params]
            data_level = self.get_txt_level('txt', task_type)
            cond = {'source': params[0]['source'], 'ocr_txt': {'$in': ocr_txts}, 'data_level': {'$lte': data_level}}
            # 统计字种
            counts = list(self.db.char.aggregate([
                {'$match': cond}, {'$group': {'_id': '$txt', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}},
            ]))
            txts = [c['_id'] for c in counts]
            # 设置当前正字
            txt = self.get_query_argument('txt', 0)
            if txt:
                cond.update({'txt': txt})
            # 查找单字数据
            docs, pager, q, order = Char.find_by_page(self, cond, default_order='cc')
            column_url = ''
            for d in docs:
                column_name = '%s_%s' % (d['page_name'], self.prop(d, 'column.cid'))
                d['column']['hash'] = h.md5_encode(column_name, self.get_config('web_img.salt'))
                if not column_url:
                    column_url = self.get_web_img(column_name, 'column')
            self.render('char_task_cluster.html', docs=docs, pager=pager, q=q, order=order,
                        char_count=self.task.get('char_count'), ocr_txts=ocr_txts,
                        txts=txts, txt=txt, column_url=column_url,
                        chars={str(d['_id']): d for d in docs})

        except Exception as error:
            return self.send_db_error(error)


class CharTaskPublishApi(CharHandler):
    URL = r'/api/char/task/publish'

    task2txt = dict(cluster_proof='ocr_txt', cluster_review='ocr_txt', separate_proof='txt',
                    separate_review='txt')

    def post(self):
        """ 发布字任务"""
        try:
            rules = [(v.not_empty, 'batch', 'task_type', 'source')]
            self.validate(self.data, rules)
            if not self.db.char.count_documents({'source': self.data['source']}):
                self.send_error_response(e.no_object, message='没有找到%s相关的字数据' % self.data['batch'])

            log = self.check_and_publish(self.data['batch'], self.data['source'], self.data['task_type'],
                                         self.data.get('num'))
            return self.send_data_response(log)

        except self.DbError as error:
            return self.send_db_error(error)

    def check_and_publish(self, batch='', source='', task_type='', num=None):
        """ 发布聚类、分类的校对、审定任务 """

        def get_task(ps, cnt, remark=None):
            priority = self.data.get('priority') or 2
            pre_tasks = self.data.get('pre_tasks') or [],
            tk = ''.join([p.get('ocr_txt') or p.get('txt') for p in ps])
            return dict(task_type=task_type, num=num, batch=batch, collection='char', id_name='name',
                        txt_kind=tk, char_count=cnt, doc_id=None, steps=None, status=self.STATUS_PUBLISHED,
                        priority=priority, pre_tasks=pre_tasks, params=ps, result={}, remark=remark,
                        create_time=self.now(), updated_time=self.now(), publish_time=self.now(),
                        publish_user_id=self.user_id, publish_by=self.username)

        def get_txt(task):
            return ''.join([str(p[field]) for p in task.get('params', [])])

        # 哪个字段
        field = self.task2txt.get(task_type)

        # 统计字频
        counts = list(self.db.char.aggregate([
            {'$match': {'source': source}}, {'$group': {'_id': '$' + field, 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
        ]))

        # 去除已发布的任务
        txts = [c['_id'] for c in counts]
        published = list(self.db.task.find({'task_type': task_type, 'num': num, 'params.' + field: {'$in': txts}}))
        if published:
            published = ''.join([get_txt(t) for t in published])
            counts = [c for c in counts if str(c['_id']) not in published]

        # 发布聚类校对-常见字
        counts1 = [c for c in counts if c['count'] >= 50]
        normal_tasks = [
            get_task([{field: c['_id'], 'count': c['count'], 'source': source}], c['count'])
            for c in counts1
        ]
        if normal_tasks:
            self.db.task.insert_many(normal_tasks)
            task_params = [t['params'] for t in normal_tasks]
            self.add_op_log(self.db, 'publish_task', dict(task_type=task_type, task_params=task_params), self.username)

        # 发布聚类校对-生僻字
        counts2 = [c for c in counts if c['count'] < 50]
        rare_tasks = []
        params, total_count = [], 0
        for c in counts2:
            total_count += c['count']
            params.append({field: c['_id'], 'count': c['count'], 'source': source})
            if total_count > 50:
                rare_tasks.append(get_task(params, total_count, '生僻字'))
                params, total_count = [], 0
        if total_count:
            rare_tasks.append(get_task(params, total_count, '生僻字'))
        if rare_tasks:
            self.db.task.insert_many(rare_tasks)
            task_params = [t['params'] for t in normal_tasks]
            self.add_op_log(self.db, 'publish_task', dict(task_type=task_type, task_params=task_params), self.username)

        return dict(published=published, normal_count=len(normal_tasks), rare_count=len(rare_tasks))


class CharTaskClusterApi(CharHandler):
    URL = ['/api/task/do/(cluster_proof|cluster_review)/@task_id',
           '/api/task/update/(cluster_proof|cluster_review)/@task_id']

    def post(self, task_type, task_id):
        """ 提交聚类校对任务"""
        try:
            # 更新char
            params = self.task['params']
            cond = {'source': params[0]['source'], 'ocr_txt': {'$in': [c['ocr_txt'] for c in params]}}
            self.db.char.update_many(cond, {'$inc': {'txt_count.' + task_type: 1}})
            # 提交任务
            self.db.task.update_one({'_id': self.task['_id']}, {'$set': {
                'status': self.STATUS_FINISHED, 'finished_time': self.now()
            }})
            self.send_data_response()

        except self.DbError as error:
            return self.send_db_error(error)

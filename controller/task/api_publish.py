#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@time: 2018/12/27
"""
import re
import controller.errors as e
import controller.validate as v
from controller.base import DbError
from controller.task.base import TaskHandler
from controller.task.publish import PublishTasksHandler


class GetReadyTasksApi(TaskHandler):
    URL = '/api/task/ready/@task_type'

    def post(self, task_type):
        """ 查找任务对应的collection，获取已就绪的数据列表 """
        assert task_type in self.task_types
        try:
            data = self.get_request_data()
            collection, id_name, input_field, shared_field = self.task_meta(task_type)
            doc_id = dict()
            if data.get('prefix'):
                doc_id.update({'$regex': '.*%s.*' % data.get('prefix'), '$options': '$i'})
            if data.get('exclude'):
                doc_id.update({'$nin': data.get('exclude')})
            condition = {id_name: doc_id} if doc_id else {}
            condition.update({input_field: {'$nin': [None, '']}})   # 任务所依赖的数据字段存在且不为空
            page_no = int(data.get('page', 0)) if int(data.get('page', 0)) > 1 else 1
            page_size = int(self.config['pager']['page_size'])
            count = self.db[collection].count_documents(condition)
            docs = self.db[collection].find(condition).limit(page_size).skip(page_size * (page_no - 1))
            response = {'docs': [d[id_name] for d in list(docs)], 'page_size': page_size,
                        'page_no': page_no, 'total_count': count}
            self.send_data_response(response)
        except DbError as err:
            self.send_db_error(err)


class PublishTasksByIdsApi(PublishTasksHandler):
    URL = r'/api/task/publish_by_ids'

    def post(self):
        """ 根据数据id发布任务。
        @param task_type 任务类型
        @param steps list，步骤
        @param pre_tasks list，前置任务
        @param ids str，待发布的任务名称
        @param priority str，1/2/3，数字越大优先级越高
        """
        data = self.get_request_data()
        rules = [
            (v.not_empty, 'doc_ids', 'task_type', 'priority', 'force'),
            (v.is_priority, 'priority'),
            (v.in_list, 'task_type', list(self.task_types.keys())),
            (v.in_list, 'pre_tasks', list(self.task_types.keys())),
        ]
        err = v.validate(data, rules)
        if err:
            return self.send_error_response(err)

        try:
            doc_ids = data['doc_ids'].split(',') if data.get('doc_ids') else []
            if len(doc_ids) > self.MAX_PUBLISH_RECORDS:
                return self.send_error_response(e.task_exceed_max, message='任务数量不能超过%s' % self.MAX_PUBLISH_RECORDS)

            force = data['force'] == '1'
            log = self.publish_task(data['task_type'], data.get('pre_tasks', []), data.get('steps', []),
                                    data['priority'], force, doc_ids=doc_ids)
            self.send_data_response({k: value for k, value in log.items() if value})

        except DbError as err:
            self.send_db_error(err)


class PublishTasksByFileApi(PublishTasksByIdsApi):
    URL = r'/api/task/publish_by_file'

    def get_request_data(self):
        ids_file = self.request.files.get('ids_file')
        ids_str = str(ids_file[0]['body'], encoding='utf-8').strip('\n') if ids_file else ''
        pre_task = self.get_body_argument('pre_tasks', '')
        steps = self.get_body_argument('steps', '')
        data = {
            'doc_ids': re.sub(r'\n+', ',', ids_str),
            'task_type': self.get_body_argument('task_type', ''),
            'priority': self.get_body_argument('priority', 1),
            'force': self.get_body_argument('force', ''),
            'pre_tasks': pre_task and pre_task.split(',') or [],
            'steps': steps and steps.split(',') or []
        }
        return data

    def post(self):
        """ 根据数据文件发布任务"""
        super().post()


class PublishTasksByPrefixApi(PublishTasksByIdsApi):
    URL = r'/api/task/publish_by_prefix'

    def get_request_data(self):
        # 根据prefix，查找数据已就绪的记录
        data = super().get_request_data()
        if not data.get('prefix') or not data.get('prefix'):
            return data
        collection, id_name, input_field, shared_field = self.task_meta(data['task_type'])
        condition = {id_name: {'$regex': '.*%s.*' % data['prefix'], '$options': '$i'},
                     input_field: {"$nin": [None, '']}}
        docs = self.db[collection].find(condition)
        doc_ids = [doc.get(id_name) for doc in docs]
        data.update({'doc_ids': doc_ids})
        return data

    def post(self):
        """ 按照前缀发布任务 """
        super().post()

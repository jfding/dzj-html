#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 发布任务
    任务对应的数据就绪后，需要设置对应的数据状态为已就绪，以便进行任务发布。
    任务发布后，将数据状态设置为已发布。任务退回或回收后，需要将数据状态重置为已就绪，以便重新发布。
@time: 2018/12/27
"""
from datetime import datetime
from controller.task.base import TaskHandler


class PublishTasksHandler(TaskHandler):
    MAX_PUBLISH_RECORDS = 10000  # 用户单次发布任务最大值

    def publish_task(self, task_type, pre_tasks, steps, priority, force, doc_ids):
        """ 发布某个任务类型的任务。
        :return 格式如下：
        { 'un_existed':[...], 'published_before':[...], 'un_ready':[...], 'published':[...], 'pending':[...],
          'publish_failed':[...], 'pending_failed':[...], 'not_published':[...] }
        """
        assert task_type in self.task_types

        log = dict()
        # 检查数据是否存在
        d = self.task_types[task_type]['data']
        collection, id_name, input_field = d['collection'], d['id'], d.get('input_field')
        docs = list(self.db[collection].find({id_name: {'$in': doc_ids}}))
        log['un_existed'] = set(doc_ids) - set([doc.get(id_name) for doc in docs])
        doc_ids = [doc.get(id_name) for doc in docs]

        # 检查数据是否已就绪
        if doc_ids and input_field:
            log['un_ready'] = [d.get(id_name) for d in docs if not d.get(input_field)]
            doc_ids = set(doc_ids) - set(log['un_ready'])

        # force为False时，检查数据是否已发布。
        # 去掉状态为OPENED\PENDING\PICKED\FINISHED的任务，留下其余状态（包括已退回或已撤回）的任务，准备发布
        if not force and doc_ids:
            ss = [self.STATUS_OPENED, self.STATUS_PENDING, self.STATUS_PICKED, self.STATUS_FINISHED]
            condition = dict(task_type=task_type, status={'$in': ss}, id_value={'$in': list(doc_ids)})
            log['published_before'] = set(t.get('id_value') for t in self.db.task.find(condition, {'id_value': 1}))
            doc_ids = set(doc_ids) - log['published_before']

        # 发布新任务
        if doc_ids:
            if pre_tasks:
                pre_tasks = [pre_tasks] if isinstance(pre_tasks, str) else pre_tasks
                for t in pre_tasks:
                    assert t in self.task_types

                # 针对前置任务均已完成的情况，发布为OPENED
                condition = dict(task_type={'$in': pre_tasks}, collection=collection, id_name=id_name,
                                 id_value={'$in': list(doc_ids)}, status=self.STATUS_FINISHED)
                tasks_finished = list(self.db.task.find(condition, {'task_type': 1, 'id_value': 1}))
                log['published'] = self._select_pre_tasks_all_finished_id_values(tasks_finished, pre_tasks)
                self._publish_task(task_type, self.STATUS_OPENED, priority, pre_tasks, steps, list(log['published']))
                doc_ids = doc_ids - log['published']

                # 其余为前置任务未发布或未完成的情况，发布为PENDING
                self._publish_task(task_type, self.STATUS_PENDING, priority, pre_tasks, steps, doc_ids)
                log['pending'] = doc_ids
            else:
                self._publish_task(task_type, self.STATUS_OPENED, priority, pre_tasks, steps, doc_ids)
                log['published'] = doc_ids

        return {k: value for k, value in log.items() if value}

    def _publish_task(self, task_type, status, priority, pre_tasks, steps, id_values):
        """ 发布新任务 """
        assert task_type in self.task_types
        task_data = self.task_types[task_type]['data']
        collection, id_name = task_data['collection'], task_data['id']
        meta = dict(task_type=task_type, collection=collection, id_name=id_name, id_value='', status=status,
                    priority=int(priority), steps=dict(todo=steps), pre_tasks={t: '' for t in pre_tasks or []},
                    input='', result='', created_time=datetime.now(), updated_time=datetime.now(),
                    publish_time=datetime.now(), publish_user_id=self.current_user['_id'],
                    publish_by=self.current_user['name'])
        tasks = []
        for id_value in id_values:
            task = meta.copy()
            task.update({'id_value': id_value})
            tasks.append(task)

        if tasks:
            self.db.task.insert_many(tasks, ordered=False)
            self.add_op_log('publish_' + task_type, context='%d个任务: %s' % (len(id_values), ','.join(id_values)))

    def _select_pre_tasks_all_finished_id_values(self, tasks_finished, pre_tasks_required):
        """ 在已完成的任务列表中，过滤出前置任务全部完成的id_value"""
        tasks = dict()
        pre_tasks_required = set(pre_tasks_required)
        for task in tasks_finished:
            if task.get('id_value') not in task:
                tasks[task.get('id_value')] = set(task.get('task_type'))
            else:
                tasks[task.get('id_value')].add(task.get('task_type'))
        id_values = [k for k, v in tasks.items() if v == pre_tasks_required]
        return set(id_values)

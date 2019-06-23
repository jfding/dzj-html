#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@time: 2019/5/13
"""
import re
from datetime import datetime
from controller.base import DbError
from tornado.escape import json_decode
from controller.task.base import TaskHandler
from controller.task.api_common import PickTaskApi as Pick


class SaveTextApi(TaskHandler):
    """ 保存文字数据。相关的任务权限、数据权限等，在prepare中已检查，无须重复检查。
        1. 保存：更新数据和任务时间即可
        2. 提交：更新数据、任务时间、任务状态、释放数据锁，然后处理后置任务
     """

    def save(self, task_type, page_name):
        try:
            assert task_type in self.text_task_names()

            data = self.get_request_data()
            data_type = self.get_data_type(task_type)
            txt = data.get('txt') and re.sub(r'\|+$', '', json_decode(data['txt']).replace('\n', '|'))

            if data.get('submit'):
                update = {
                    data_type: txt,
                    'tasks.%s.status' % task_type: self.STATUS_FINISHED,
                    'tasks.%s.updated_time' % task_type: datetime.now(),
                    'tasks.%s.finished_time' % task_type: datetime.now(),
                    'lock.%s' % data_type: None,
                }
            else:
                update = {
                    data_type: txt,
                    'tasks.%s.updated_time' % task_type: datetime.now(),
                }

            r = self.db.page.update_one({'name': page_name}, {'$set': update})
            if r.modified_count:
                self.add_op_log('save_' + task_type, context=page_name)

            if data.get('submit'):
                # 处理后置任务
                self.update_post_tasks(page_name, task_type)

        except DbError as e:
            self.send_db_error(e)


class SaveTextProofApi(SaveTextApi):
    URL = '/api/task/do/text_proof_@num/@page_name'

    def post(self, num, page_name):
        """ 保存或提交文字校对任务 """
        self.save('text_proof_' + num)
        if self.get_request_data().get('submit'):
            Pick.pick(self, 'text_proof_' + num)


class SaveTextReviewApi(SaveTextApi):
    URL = '/api/task/do/text_review/@page_name'

    def post(self, num, page_name):
        """ 保存或提交文字审定任务 """
        self.save('text_review')
        if self.get_request_data().get('submit'):
            Pick.pick(self, 'text_review')

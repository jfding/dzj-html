#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 我的任务
@time: 2018/12/26
"""
from controller.task.base import TaskHandler


class MyTaskHandler(TaskHandler):
    URL = '/task/my/@task_type'

    def get(self, task_type):
        """ 我的任务 """
        try:
            q = self.get_query_argument('q', '').upper()
            order = self.get_query_argument('order', '-picked_time')
            page_size = int(self.config['pager']['page_size'])
            cur_page = int(self.get_query_argument('page', 1))
            tasks, total_count = self.get_my_tasks_by_type(
                task_type=task_type, name=q, order=order, page_size=page_size, page_no=cur_page
            )
            pager = dict(cur_page=cur_page, item_count=total_count, page_size=page_size)
            self.render('my_task.html', task_type=task_type, tasks=tasks, pager=pager, order=order,
                        select_my_text_proof=self.select_my_text_proof)
        except Exception as e:
            return self.send_db_error(e, render=True)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tests.users as u
from tests.testcase import APITestCase
from controller import errors
from controller.task.base import TaskHandler
from controller.task.api_admin import PublishTasksApi
from tornado.escape import json_encode


class TestTaskFlow(APITestCase):
    def setUp(self):
        super(TestTaskFlow, self).setUp()

        # 创建几个专家用户（权限足够），用于审校流程的测试
        self.add_first_user_as_admin_then_login()
        self.add_users_by_admin([dict(email=r[0], name=r[2], password=r[1])
                                 for r in [u.expert1, u.expert2, u.expert3]],
                                ','.join(['切分专家', '文字专家']))

    def tearDown(self):
        # 退回所有任务，还原改动
        for task_type in TaskHandler.task_types.keys():
            self.assert_code(200, self.fetch('/api/task/unlock/%s/' % task_type))
        for i in range(1, 4):
            self.assert_code(200, self.fetch('/api/task/unlock/text_proof.%d/' % i))

        super(TestTaskFlow, self).tearDown()

    def publish(self, task_type, data):
        return self.fetch('/api/task/publish/%s' % task_type, body={'data': data})

    def _set_page_status(self, page_names, task_type, status):
        condition = {'name': {'$in': page_names}}
        update_value = PublishTasksApi.get_status_update(task_type, status)
        self._app.db.page.update_many(condition, {'$set': update_value})

    def _test_publish_task(self, task_type):

        # 测试页面为空
        r = self.parse_response(self.publish(task_type, dict(pages='')))
        self.assertIsInstance(r['data'], dict)
        self.assertFalse(hasattr(r['data'], 'published'))

        # 测试不存在的页面
        pages_not_existed = ['GL_not_existed_1', 'JX_not_existed_2']
        r = self.parse_response(self.publish(task_type, dict(pages=','.join(pages_not_existed), priority='高')))
        self.assertEqual(pages_not_existed, r['data']['not_existed'])

        # 测试未就绪的页面
        pages_not_ready = ['GL_1056_5_6', 'JX_165_7_12', 'JX_165_7_30', 'JX_165_7_75', 'JX_165_7_87']
        self._set_page_status(pages_not_ready, task_type, TaskHandler.STATUS_UNREADY)
        r = self.parse_response(self.publish(task_type, dict(pages=','.join(pages_not_ready), priority='高')))
        self.assertEqual(pages_not_ready, r['data']['not_ready'])

        # 测试已就绪的页面
        pages_ready = ['QL_25_16', 'QL_25_313', 'QL_25_416', 'QL_25_733', 'YB_22_346', 'YB_22_389']
        self._set_page_status(pages_ready, task_type, TaskHandler.STATUS_READY)
        r = self.parse_response(self.publish(task_type, dict(pages=','.join(pages_ready), priority='高')))
        status = 'pending' if TaskHandler.pre_tasks().get(task_type) else 'published'
        self.assertEqual(pages_ready, r['data'][status])
        self._set_page_status(pages_ready, task_type, TaskHandler.STATUS_READY)

        # 测试已发布的页面
        pages_published = ['YB_22_713', 'YB_22_759', 'YB_22_816', 'YB_22_916', 'YB_22_995']
        self._set_page_status(pages_published, task_type, TaskHandler.STATUS_OPENED)
        r = self.parse_response(self.publish(task_type, dict(pages=','.join(pages_published), priority='高')))
        self.assertEqual(pages_published, r['data']['published_before'])

        # 组合测试
        all_pages = pages_not_existed + pages_not_ready + pages_ready + pages_published
        self._set_page_status(pages_not_ready, task_type, TaskHandler.STATUS_UNREADY)
        self._set_page_status(pages_ready, task_type, TaskHandler.STATUS_READY)
        self._set_page_status(pages_published, task_type, TaskHandler.STATUS_OPENED)
        r = self.parse_response(self.publish(task_type, dict(pages=','.join(all_pages), priority='高')))
        self.assertEqual(pages_not_existed, r['data']['not_existed'])
        self.assertEqual(pages_not_ready, r['data']['not_ready'])
        self.assertEqual(pages_ready, r['data'][status])
        self.assertEqual(pages_published, r['data']['published_before'])

        # 还原页面状态
        self._set_page_status(pages_not_ready, task_type, TaskHandler.STATUS_READY)
        self._set_page_status(pages_published, task_type, TaskHandler.STATUS_READY)

    def test_publish_tasks(self):
        """ 测试发布审校任务 """
        self.add_first_user_as_admin_then_login()
        self._test_publish_task('block_cut_proof')  # 测试一级任务
        self._test_publish_task('block_cut_review')  # 测试一级任务有前置任务的情况
        self._test_publish_task('text_proof')  # 测试一级任务有子任务的情况
        self._test_publish_task('text_proof.1')  # 测试二级任务

    def test_task_lobby(self):
        """ 测试任务大厅 """

        self.login_as_admin()
        for task_type in ['block_cut_proof', 'column_cut_proof', 'char_cut_proof', 'block_cut_review',
                          'column_cut_review', 'char_cut_review', 'text_proof', 'text_review']:
            if task_type == 'text_proof':
                for i in range(1, 4):
                    r = self.parse_response(self.publish('%s.%d' % (task_type, i),
                                                         dict(pages='GL_1056_5_6,JX_165_7_12')))
            else:
                r = self.parse_response(self.publish(task_type, dict(pages='GL_1056_5_6,JX_165_7_12')))
            published = r.get('data', {}).get('published')
            pending = r.get('data', {}).get('pending')
            if 'cut_proof' in task_type:
                self.assertIsInstance(published, list, msg=task_type)
                self.assertEqual({'GL_1056_5_6', 'JX_165_7_12'}, set(published), msg=task_type)
            elif 'cut_review' in task_type:
                self.assertIsInstance(pending, list, msg=task_type)
                self.assertEqual({'GL_1056_5_6', 'JX_165_7_12'}, set(pending), msg=task_type)

            r = self.fetch('/task/lobby/%s?_raw=1&_no_auth=1' % task_type)
            self.assert_code(200, r, msg=task_type)
            r = self.parse_response(r)
            if published:
                self.assertEqual({'GL_1056_5_6', 'JX_165_7_12'}, set([t['name'] for t in r['tasks']]), msg=task_type)

            self.assert_code(200, self.fetch('/api/task/unlock/cut/'))
            self.assert_code(200, self.fetch('/api/task/unlock/text/'))

    def test_cut_proof(self):
        """ 测试切分校对的任务领取、保存和提交 """

        for task_type in TaskHandler.cut_task_names:
            # 发布任务
            self.login_as_admin()
            self.assert_code(200, self.fetch('/api/task/unlock/cut/'))
            self.assert_code(200, self.publish(task_type, dict(pages='GL_1056_5_6,JX_165_7_12')))

            # 任务大厅
            self.login(u.expert1[0], u.expert1[1])
            r = self.parse_response(self.fetch('/task/lobby/%s?_raw=1' % task_type))
            tasks = r.get('tasks')
            if 'cut_review' in task_type:
                self.assertEqual(tasks, [], msg=task_type)
                continue
            self.assertEqual({'GL_1056_5_6', 'JX_165_7_12'}, set([t['name'] for t in tasks]), msg=task_type)

            # 领取任务
            r = self.parse_response(self.fetch('/api%s' % tasks[0]['pick_url']))
            self.assertIn('url', r)
            r = self.parse_response(self.fetch('%s?_raw=1' % r['url']))
            page = r.get('page')
            self.assertIn(task_type, page)
            self.assertEqual(page[task_type]['status'], 'picked')
            self.assertEqual(page[task_type]['picked_by'], u.expert1[2])

            # 再领取新任务就提示有未完成任务
            r = self.parse_response(self.fetch('/api%s' % tasks[1]['pick_url']))
            self.assertEqual(errors.task_uncompleted[0], r.get('code'))

            # 其他人不能领取此任务
            self.login(u.expert2[0], u.expert2[1])
            r = self.parse_response(self.fetch('/task/lobby/%s?_raw=1' % task_type))
            self.assertNotIn(page['name'], [t['name'] for t in r.get('tasks')])
            r = self.fetch('/task/do/%s/%s?_raw=1' % (task_type, page['name']))
            self.assert_code(errors.task_picked, r)

            # 保存
            self.login(u.expert1[0], u.expert1[1])
            box_type = task_type.split('_')[0]
            boxes = page[box_type + 's']
            r = self.fetch('/api/task/save/%s?_raw=1' % (task_type,),
                           body={'data': dict(name=page['name'], box_type=box_type, boxes=json_encode(boxes))})
            self.assert_code(200, r)
            self.assertFalse(self.parse_response(r).get('box_changed'))

            boxes[0]['w'] += 1
            r = self.fetch('/api/task/save/%s?_raw=1' % (task_type,),
                           body={'data': dict(name=page['name'], box_type=box_type, boxes=json_encode(boxes))})
            self.assertTrue(self.parse_response(r).get('box_changed'))

            # 提交
            boxes[0]['w'] -= 1
            r = self.fetch('/api/task/save/%s?_raw=1' % (task_type,),
                           body={'data': dict(name=page['name'], submit=True,
                                              box_type=box_type, boxes=json_encode(boxes))})
            self.assert_code(200, r)
            self.assertTrue(self.parse_response(r).get('submitted'))

    def test_cut_relation(self):
        """ 测试切分审校的前后依赖关系 """

        # 发布两个栏切分审校任务
        self.login_as_admin()
        self.assert_code(200, self.publish('block_cut_proof', dict(pages='GL_1056_5_6,JX_165_7_12')))
        tasks = self.parse_response(self.fetch('/task/lobby/block_cut_proof?_raw=1'))['tasks']
        self.assert_code(200, self.publish('block_cut_review', dict(pages='GL_1056_5_6,JX_165_7_12')))

        # 领取并提交
        self.login(u.expert1[0], u.expert1[1])
        r = self.parse_response(self.fetch('/api%s' % tasks[0]['pick_url']))
        self.assertIn('url', r, str(r))
        r = self.parse_response(self.fetch('%s?_raw=1' % r['url']))
        page = r['page']
        self.assertIn('name', page)
        r = self.fetch('/api/task/save/block_cut_proof?_raw=1',
                       body={'data': dict(name=page['name'], submit=True,
                                          box_type='block', boxes=json_encode(page['blocks']))})
        r = self.parse_response(r)
        self.assertRegex(r.get('jump'), r'^/task/do/')
        self.assertIn(tasks[1]['name'], r.get('jump'))
        self.assertEqual(r.get('resume_next'), 'block_cut_review')

    def test_pick_text_proof_task(self):
        """ 测试文字校对任务的领取和提交 """

        # 发布一个页面的校一、校二任务
        self.login_as_admin()
        self.fetch('/api/task/unlock/text_proof/')
        r1 = self.parse_response(self.publish('text_proof.1', dict(pages='GL_1056_5_6')))
        r2 = self.parse_response(self.publish('text_proof.2', dict(pages='GL_1056_5_6')))
        self.assertEqual(r1.get('published'), ['GL_1056_5_6'])
        self.assertEqual(r2.get('published'), ['GL_1056_5_6'])

        # 多次领取的是同一个任务
        self.login(u.expert1[0], u.expert1[1])
        self.assert_code(200, self.fetch('/api/task/pick/text_proof.1/GL_1056_5_6'))
        r1 = self.fetch('/api/task/pick/text_proof/GL_1056_5_6')
        self.assert_code(200, r1)
        r2 = self.fetch('/api/task/pick/text_proof/GL_1056_5_6')
        self.assert_code(200, r2)
        r1, r2 = self.parse_response(r1), self.parse_response(r2)
        self.assertEqual(r1['url'], r2['url'])

        # 让此任务完成
        r = self.parse_response(self.fetch('%s?_raw=1' % r1['url']))
        page = r.get('page')
        self.assertIn('name', page)
        r = self.fetch('/api/task/save/text_proof/%s?_raw=1' % r1['url'].split('/')[-2],
                       body={'data': dict(name=page['name'], submit=True,
                                          chars=json_encode(page['chars']))})
        self.assert_code(200, r)
        # 页面相同，不能再自动领另一个校次的
        self.assertFalse(self.parse_response(r).get('jump'))

        # 已完成的任务还可以再次继续编辑，任务状态不变
        r = self.parse_response(self.fetch('%s?_raw=1' % r1['url']))
        p2 = r.get('page') or {}
        self.assertEqual(p2.get('name'), page['name'])

        p = self.parse_response(self.fetch('/api/task/page/' + page['name']))
        self.assertEqual(TaskHandler.get_obj_property(p, r['task_type'] + '.status'), TaskHandler.STATUS_FINISHED)

    def test_text_returned_pick(self):
        """测试先退回文字校对任务再领取同一页面的文字校对任务"""

        # 发布两个校次的文字校对任务
        self.login_as_admin()
        self.fetch('/api/task/unlock/text_proof/')
        self.assert_code(200, self.publish('text_proof.1', dict(pages='GL_1056_5_6,JX_165_7_12')))
        self.assert_code(200, self.publish('text_proof.2', dict(pages='GL_1056_5_6')))

        # 领取一个任务
        self.login(u.expert1[0], u.expert1[1])
        self.assert_code(200, self.fetch('/api/task/pick/text_proof.1/GL_1056_5_6'))
        p = self.parse_response(self.fetch('/api/task/page/GL_1056_5_6'))
        self.assertEqual(TaskHandler.get_obj_property(p, 'text_proof.1.status'), TaskHandler.STATUS_PICKED)

        # 再领取相同任务则结果不变
        r = self.parse_response(self.fetch('/api/task/pick/text_proof.1/GL_1056_5_6'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/1/GL_1056_5_6')

        # 再领取别的任务则结果不变
        r = self.parse_response(self.fetch('/api/task/pick/text_proof.2/GL_1056_5_6'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/1/GL_1056_5_6')
        r = self.parse_response(self.fetch('/api/task/pick/text_proof.1/JX_165_7_12'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/1/GL_1056_5_6')
        r = self.parse_response(self.fetch('/api/task/pick/text_proof/GL_1056_5_6'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/1/GL_1056_5_6')

        # 退回任务后领取相同页面的其他校次任务

        self.assert_code(200, self.fetch('/api/task/unlock/text_proof.1/GL_1056_5_6'))
        p = self.parse_response(self.fetch('/api/task/page/GL_1056_5_6'))
        self.assertEqual(TaskHandler.get_obj_property(p, 'text_proof.1.status'), TaskHandler.STATUS_READY)
        self.assertIsNone(TaskHandler.get_obj_property(p, 'text_proof.1.picked_user_id'))
        self.assertIsNone(TaskHandler.get_obj_property(p, 'text_proof.1.picked_by'))

        r = self.parse_response(self.fetch('/api/task/pick/text_proof.2/GL_1056_5_6'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/2/GL_1056_5_6')

        self.assert_code(200, self.fetch('/api/task/unlock/text_proof.2/GL_1056_5_6', body={}))
        p = self.parse_response(self.fetch('/api/task/page/GL_1056_5_6'))
        self.assertEqual(TaskHandler.get_obj_property(p, 'text_proof.2.status'), TaskHandler.STATUS_RETURNED)
        self.assertIsNone(TaskHandler.get_obj_property(p, 'text_proof.2.picked_user_id'))
        self.assertTrue(TaskHandler.get_obj_property(p, 'text_proof.2.picked_by'))

        r = self.parse_response(self.fetch('/api/task/pick/text_proof.2/GL_1056_5_6'))
        self.assertEqual(r.get('url'), '/task/do/text_proof/2/GL_1056_5_6')

        p = self.parse_response(self.fetch('/api/task/page/GL_1056_5_6'))
        self.assertEqual(TaskHandler.get_obj_property(p, 'text_proof.2.status'), TaskHandler.STATUS_PICKED)

    def test_lobby_order(self):
        """测试任务大厅的任务显示顺序"""
        self.login_as_admin()
        self.fetch('/api/task/unlock/text_proof/')
        self.publish('text_proof.1', dict(pages='GL_1056_5_6', priority='中'))
        self.publish('text_proof.2', dict(pages='JX_165_7_12', priority='高'))
        self.publish('text_proof.2', dict(pages='JX_165_7_30', priority='中'))
        self.publish('text_proof.3', dict(pages='JX_165_7_12', priority='高'))

        self.login(u.expert1[0], u.expert1[1])
        for i in range(5):
            r = self.parse_response(self.fetch('/task/lobby/text_proof?_raw=1'))
            names = [t['name'] for t in r.get('tasks', [])]
            self.assertEqual(set(names), {'GL_1056_5_6', 'JX_165_7_12', 'JX_165_7_30'})
            self.assertEqual(names[0], 'JX_165_7_12')

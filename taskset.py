#!/usr/bin/env python

"""
taskset.py - parser for task set from JSON file
"""

import json
import sys


class TaskSetJsonKeys(object):
    # Task set
    KEY_TASKSET = "taskset"

    # Task
    KEY_TASK_ID = "taskId"
    KEY_TASK_PERIOD = "period"
    KEY_TASK_WCET = "wcet"
    KEY_TASK_DEADLINE = "deadline"
    KEY_TASK_OFFSET = "offset"
    KEY_TASK_SECTIONS = "sections"

    # Schedule
    KEY_SCHEDULE_START = "startTime"
    KEY_SCHEDULE_END = "endTime"

    # Release times
    KEY_RELEASETIMES = "releaseTimes"
    KEY_RELEASETIMES_JOBRELEASE = "timeInstant"
    KEY_RELEASETIMES_TASKID = "taskId"


class TaskSetIterator:
    def __init__(self, taskSet):
        self.taskSet = taskSet
        self.index = 0
        self.keys = iter(taskSet.tasks)

    def __next__(self):
        key = next(self.keys)
        return self.taskSet.tasks[key]


class TaskSet(object):
    def __init__(self, data):
        self.parseDataToTasks(data)
        self.buildJobReleases(data)

    def parseDataToTasks(self, data):
        taskSet = {}

        for taskData in data[TaskSetJsonKeys.KEY_TASKSET]:
            task = Task(taskData)

            if task.id in taskSet:
                print("Error: duplicate task ID: {0}".format(task.id))
                return

            if task.period < 0 and task.relativeDeadline < 0:
                print("Error: aperiodic task must have positive relative deadline")
                return

            taskSet[task.id] = task

        self.tasks = taskSet

    def buildJobReleases(self, data):
        jobs = []

        if TaskSetJsonKeys.KEY_RELEASETIMES in data:  # necessary for sporadic releases
            for jobRelease in data[TaskSetJsonKeys.KEY_RELEASETIMES]:
                releaseTime = float(jobRelease[TaskSetJsonKeys.KEY_RELEASETIMES_JOBRELEASE])
                taskId = int(jobRelease[TaskSetJsonKeys.KEY_RELEASETIMES_TASKID])

                job = self.getTaskById(taskId).spawnJob(releaseTime)
                jobs.append(job)
        else:
            scheduleStartTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_START])
            scheduleEndTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_END])
            for task in self:
                t = max(task.offset, scheduleStartTime)
                while t < scheduleEndTime:
                    job = task.spawnJob(t)
                    if job is not None:
                        jobs.append(job)

                    if task.period >= 0:
                        t += task.period  # periodic
                    else:
                        t = scheduleEndTime  # aperiodic

        self.jobs = jobs

    def __contains__(self, elt):
        return elt in self.tasks

    def __iter__(self):
        return TaskSetIterator(self)

    def __len__(self):
        return len(self.tasks)

    def getTaskById(self, taskId):
        return self.tasks[taskId]

    def printTasks(self):
        print("\nTask Set:")
        for task in self:
            print(task)

    def printJobs(self):
        print("\nJobs:")
        for task in self:
            for job in task.getJobs():
                print(job)


class Task(object):
    def __init__(self, taskDict):
        self.id = int(taskDict[TaskSetJsonKeys.KEY_TASK_ID])
        self.period = float(taskDict[TaskSetJsonKeys.KEY_TASK_PERIOD])
        self.wcet = float(taskDict[TaskSetJsonKeys.KEY_TASK_WCET])
        self.relativeDeadline = float(
            taskDict.get(TaskSetJsonKeys.KEY_TASK_DEADLINE, taskDict[TaskSetJsonKeys.KEY_TASK_PERIOD]))
        self.offset = float(taskDict.get(TaskSetJsonKeys.KEY_TASK_OFFSET, 0.0))
        self.sections = taskDict[TaskSetJsonKeys.KEY_TASK_SECTIONS]
        # for i in range(len(self.sections)):
        #     self.sections[i][0] = int(self.sections[i][0])
        #     self.sections[i][1] = float(self.sections[i][1])
        #     self.sections[i] = tuple(self.sections[i])

        self.lastJobId = 0
        self.lastReleasedTime = 0.0

        self.jobs = []

    def getAllResources(self):
        result = []
        for section in self.sections:
            if section[0] not in result and section[0] != 0:
                result.append(section[0])
        return result

    def spawnJob(self, releaseTime):
        if self.lastReleasedTime > 0 and releaseTime < self.lastReleasedTime:
            print("INVALID: release time of job is not monotonic")
            return None

        if self.lastReleasedTime > 0 and releaseTime < self.lastReleasedTime + self.period:
            print("INVDALID: release times are not separated by period")
            return None

        self.lastJobId += 1
        self.lastReleasedTime = releaseTime

        job = Job(self, self.lastJobId, releaseTime)

        self.jobs.append(job)
        return job

    def getJobs(self):
        return self.jobs

    def getJobById(self, jobId):
        if jobId > self.lastJobId:
            return None

        job = self.jobs[jobId - 1]
        if job.id == jobId:
            return job

        for job in self.jobs:
            if job.id == jobId:
                return job

        return None

    def getUtilization(self):
        return self.wcet / self.period

    def __str__(self):
        return "task {0}: (Φ,T,C,D,∆) = ({1}, {2}, {3}, {4}, {5})".format(self.id, self.offset, self.period, self.wcet,
                                                                          self.relativeDeadline, self.sections)


class Job(object):
    def __init__(self, task, jobId, releaseTime):
        self.task = task
        self.id = jobId
        self.releaseTime = releaseTime
        self.deadline = releaseTime + task.relativeDeadline
        # self.resourceHeld = None
        self.isActive = False

        self.remainingTime = self.task.wcet

    def getResourceHeld(self):
        '''the resources that it's currently holding'''
        executedTime = self.task.wcet - self.remainingTime
        # print("executedTime = " + str(executedTime))
        # raise Exception
        for section in self.task.sections:
            if executedTime == 0:
                if self.isActive:
                    if section[0] == 0:
                        return None
                    return section[0]
                else:
                    return None
            if section[1] <= executedTime:  # this section has passed
                executedTime -= section[1]
                continue
            elif section[0] == 0:  # current section holding no resource
                return None
            else:  # in a critical section
                return section[0]

    def getRecourseWaiting(self):
        '''a resource that is being waited on, but not currently executing'''
        executedTime = self.task.wcet - self.remainingTime
        for section in self.task.sections:
            if section[1] <= executedTime:  # this section has passed
                executedTime -= section[1]
                continue
            elif executedTime < 0 or section[0] == 0:  # in the middle of a section, or next section uses no resource
                return None
            elif executedTime == 0:  # waiting on a resource
                return section[0]

    def getRemainingSectionTime(self):
        executedTime = self.task.wcet - self.remainingTime
        for section in self.task.sections:
            if executedTime == 0:  # job has not started
                return section[1]
            elif section[1] <= executedTime:  # this section has passed
                executedTime -= section[1]
                continue
            else:
                return section[1] - executedTime
        return 0

    def execute(self, time):
        executionTime = min(self.remainingTime, time)
        self.remainingTime -= executionTime
        return executionTime

    def executeToCompletion(self):
        return self.execute(self.remainingTime)

    def isCompleted(self):
        return self.remainingTime == 0

    def __str__(self):
        return "[{0}:{1}] released at {2} -> deadline at {3}".format(self.task.id, self.id, self.releaseTime,
                                                                     self.deadline)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "taskset1.json"

    with open(file_path) as json_data:
        data = json.load(json_data)

    taskSet = TaskSet(data)

    taskSet.printTasks()
    taskSet.printJobs()

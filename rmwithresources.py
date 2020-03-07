#!/usr/bin/env python

"""
rm.py - Rate Monotonic scheduler

RmPriorityQueue: priority queue that prioritizes by period
RmScheduler: scheduling algorithm that executes RM
"""

import json
import sys

from taskset import *
from scheduleralgorithm import *
from schedule import ScheduleInterval, Schedule
from display import SchedulingDisplay

class RmPriorityQueue(PriorityQueue):
    def __init__(self, jobReleaseDict, taskSet):
        """
        Creates a priority queue of jobs ordered by period.
        """
        PriorityQueue.__init__(self, jobReleaseDict)
        self.resourceCeilings = {}
        self.resources = []

        for task in taskSet:
            for resource in task.getAllResources():
                if resource not in self.resources:
                    self.resources.append(resource)
                    self.resourceCeilings[resource] = task.period
                elif self.resourceCeilings[resource] > task.period:
                    self.resourceCeilings[resource] = task.period

        self.protocol = 'HLP'

        self._sortQueue()

    def setProtocol(self, protocol):
        self.protocol = protocol

    def _sortQueue(self):
        # RM orders by period
        self._updateActivePriorities()

        self.jobs.sort(key = lambda x: (self.activePriorities[x], x.task.id, x.id))

    def _updateActivePriorities(self):
        if self.protocol == 'HLP':
            self._updateActivePrioritiesHLP()
        else:
            self._updateActivePrioritiesPIP()

    def _updateActivePrioritiesHLP(self):
        self.activePriorities = {}
        for job in self.jobs:
            if job.getResourceHeld() is not None:
                self.activePriorities[job] = self.resourceCeilings[job.getResourceHeld()]
                #print(str(job) + " holds " + str(job.getResourceHeld()) + ";" + " its active prio is " + str(self.activePriorities[job]))
            else:
                self.activePriorities[job] = job.task.period

    def _updateActivePrioritiesPIP(self):
        self.resourceCeilings = {}
        self.activePriorities = {}
        for job in self.jobs:
            if job.getRecourseWaiting() is not None:
                resource = job.getRecourseWaiting()
                if resource not in self.resourceCeilings:
                    self.resourceCeilings[resource] = job.task.period
                else:
                    self.resourceCeilings[resource] = min(self.resourceCeilings[resource], job.task.period)

        for resource in self.resources:
            if resource not in self.resourceCeilings:
                self.resourceCeilings[resource] = float('inf')

        for job in self.jobs:
            if job.getResourceHeld() is not None:
                self.activePriorities[job] = min(self.resourceCeilings[job.getResourceHeld()], job.task.period)
            else:
                self.activePriorities[job] = job.task.period

    def _findFirst(self, t):
        """
        Returns the index of the highest-priority job released at or before t,
        or -1 if the queue is empty or if all remaining jobs are released after t.
        """
        if self.isEmpty():
            return -1

        self._updateActivePriorities()

        currentJobs = [(i, job) for (i,job) in enumerate(self.jobs) if job.releaseTime <= t]
        if len(currentJobs) == 0:
            return -1

        currentJobs.sort(key = lambda x: (self.activePriorities[x[1]], x[1].task.id, x[1].id))

        if self.protocol == 'PIP':
            highestActive = self.activePriorities[currentJobs[0][1]]
            highestJobs = []
            for (i, job) in currentJobs:
                if self.activePriorities[job] == highestActive:
                    highestJobs.append((i, job))
            #highestJobs = filter(lambda x: self.activePriorities[x[1]] == self.activePriorities[x[1]], currentJobs)
            for (i, job) in highestJobs:
                if job.getResourceHeld() is not None:
                    return i

        return currentJobs[0][0] # get the index from the tuple in the 0th position

    def popNextJob(self, t):
        """
        Removes and returns the highest-priority job of those released at or after t,
        or None if no jobs are released at or after t.
        """
        laterJobs = [(i, job) for (i,job) in enumerate(self.jobs) if job.releaseTime >= t]

        if len(laterJobs) == 0:
            return None

        self._updateActivePriorities()

        laterJobs.sort(key = lambda x: (x[1].releaseTime, self.activePriorities[x[1]], x[1].task.id))
        return self.jobs.pop(laterJobs[0][0]) # get the index from the tuple in the 0th position

    def popPreemptingJob(self, t, job):
        """
        Removes and returns the job that will preempt job 'job' after time 't', or None
        if no such preemption will occur (i.e., if no higher-priority jobs
        are released before job 'job' will finish executing).

        t: the time after which a preemption may occur
        job: the job that is executing at time 't', and which may be preempted
        """

        #print("checking for preempts at " + str(t))
        self._updateActivePriorities()

        if job.getResourceHeld() is not None:
            self.activePriorities[job] = min(self.resourceCeilings[job.getResourceHeld()], job.task.period)
            #print(str(job) + " holds " + str(job.getResourceHeld()) + ";" + " its active prio is " + str(self.activePriorities[job]))
        else:
            self.activePriorities[job] = job.task.period


        hpJobs = [(i, j) for (i,j) in enumerate(self.jobs) if \
                  ((self.activePriorities[j] < self.activePriorities[job]) and \
                   t < j.releaseTime < t + job.getRemainingSectionTime())]

        #print(hpJobs)

        if len(hpJobs) == 0:
            return None

        hpJobs.sort(key = lambda x: (x[1].releaseTime, self.activePriorities[x[1]], x[1].task.id))
        # result = self.jobs.pop(hpJobs[0][0])
        # # print(result)
        # return result
        return self.jobs.pop(hpJobs[0][0]) # get the index from the tuple in the 0th position


class RmScheduler(SchedulerAlgorithm):
    def __init__(self, taskSet):
        SchedulerAlgorithm.__init__(self, taskSet)

    def buildSchedule(self, startTime, endTime, protocol='HLP'):

        self._buildPriorityQueue(RmPriorityQueue)
        if protocol == 'PIP':
            self.priorityQueue.setProtocol(protocol)

        time = 0.0
        self.schedule.startTime = time

        previousJob = None
        didPreemptPrevious = False

        # Loop until the priority queue is empty, executing jobs preemptively in RM order
        while not self.priorityQueue.isEmpty():
            # Make a scheduling decision resulting in an interval
            interval, newJob = self._makeSchedulingDecision(time, previousJob)

            if previousJob is not None:
                previousJob.isActive = False
            if newJob is not None:
                newJob.isActive = True
            if newJob is not None:
                interval.resource = newJob.getResourceHeld()
            # interval.jobCompleted = newJob.isCompleted()
            # if interval.jobCompleted:
            #     pass


            nextTime = interval.startTime
            didPreemptPrevious = interval.didPreemptPrevious

            # If the previous interval wasn't idle, execute the previous job
            # until the start of the new interval
            # if previousJob is not None:
            #
            #
            #     # If a preemption occurred, put the previous job back in the
            #     # priority queue
            #     if not previousJob.isCompleted() and not interval.didPreemptPrevious:
            #         previousJob.execute(interval.startTime - time)
            #         self.priorityQueue.addJob(previousJob)

            # Add the interval to the schedule
            self.schedule.addInterval(interval)

            # Update the time and job
            time = nextTime
            previousJob = newJob

        # If there is still a previous job, complete it and update the time
        if previousJob is not None:
            time += previousJob.remainingTime
            previousJob.executeToCompletion()

        #interval.resource = newJob.getResourceHeld()
        #interval.jobCompleted = newJob.isCompleted()

        # Add the final idle interval
        finalInterval = ScheduleInterval()
        finalInterval.intialize(time, None, False)
        self.schedule.addInterval(finalInterval)

        finalInterval.resource = None
        finalInterval.jobCompleted = False

        # Post-process the intervals to set the end time and whether the job completed
        latestDeadline = max([job.deadline for job in self.taskSet.jobs])
        endTime = max(time + 1.0, latestDeadline, float(endTime))
        self.schedule.postProcessIntervals(endTime)

        return self.schedule

    def _makeSchedulingDecision(self, t, previousJob):
        """
        Makes a scheduling decision after time t.

        t: the beginning of the previous time interval, if one exists (or 0 otherwise)
        previousJob: the job that was previously executing, and will either complete or be preempted

        returns: (ScheduleInterval instance, Job instance of new job to execute)
        """
        if previousJob is None:
            # If there was no previous job, the last interval was an idle one
            newJob = self.priorityQueue.popNextJob(t)
            nextTime = newJob.releaseTime
            doesPreempt = False
        else:
            # If a job will preempt the previous job (due to the new job's
            # release), find that job
            preemptingJob = self.priorityQueue.popPreemptingJob(t, previousJob)

            if (preemptingJob is not None) and (previousJob.remainingTime == preemptingJob.releaseTime - t):
                # No preemption occurs
                intervalDuration = previousJob.remainingTime
                nextTime = t + intervalDuration
                doesPreempt = False

                newJob = preemptingJob
            elif (preemptingJob is None):
                # No preemption occurs
                intervalDuration = previousJob.getRemainingSectionTime()

                nextTime = t + intervalDuration
                doesPreempt = False

                # Choose a new job to execute (if None, this will be an idle interval)
                previousJob.execute(intervalDuration)
                if not previousJob.isCompleted():
                    self.priorityQueue.addJob(previousJob)

                previousJob.isActive = False
                newJob = self.priorityQueue.popFirst(nextTime)


            else:
                # A preemption occurs
                nextTime = preemptingJob.releaseTime
                doesPreempt = True

                newJob = preemptingJob

                intervalDuration = nextTime - t
                previousJob.execute(intervalDuration)
                if not previousJob.isCompleted():
                    self.priorityQueue.addJob(previousJob)

        # Build the schedule interval
        interval = ScheduleInterval()
        interval.intialize(nextTime, newJob, doesPreempt)

        return interval, newJob

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "taskset3.json"

    with open(file_path) as json_data:
        data = json.load(json_data)

    taskSet = TaskSet(data)

    taskSet.printTasks()
    taskSet.printJobs()

    rm = RmScheduler(taskSet)
    if len(sys.argv) == 3:
        schedule = rm.buildSchedule(0, 6, sys.argv[2])
    else:
        schedule = rm.buildSchedule(0, 6)

    schedule.printIntervals(displayIdle=True)

    print("\n// Validating the schedule:")
    schedule.checkWcets()
    schedule.checkFeasibility()

    display = SchedulingDisplay(width=800, height=480, fps=33, scheduleData=schedule)
    display.run()

#!/usr/bin/env python

"""
schedulability.py - suite of schedulability tests
"""

from taskset import TaskSetJsonKeys, Task, TaskSet
import rmwithresources

import matplotlib.pyplot as plt
import random

def getUniformValue(a, b):
    """
    Returns a value uniformly selected from the range [a,b].
    """
    return random.uniform(a,b)

# Per-task utilization functions
lightUtilFunc = lambda : getUniformValue(0.001, 0.01)
mediumLightUtilFunc = lambda : getUniformValue(0.01, 0.1)
mediumUtilFunc = lambda : getUniformValue(0.1, 0.4)

newUtilFunc = lambda : 0.7

# periods are in milliseconds
shortPeriodFunc = lambda : getUniformValue(3, 33)
longPeriodFunc = lambda : getUniformValue(50, 250)
choicePeriodFunc = lambda : random.choice([250, 500, 750, 1000, 1500, 2000, 6000])

sectionlengthFunc = lambda : getUniformValue(10, 100)

def generateRandomTaskSet(targetUtil, utilFunc, periodFunc, numresources):
    """
    Generates a random task set with total utilization targetUtil.

    Just returns the task set as a list of Task objects, rather than
    the proper TaskSet type.
    """
    utilSum = 0

    # Generate tasks until the utilization target is met
    taskSet = []
    i = 0
    while utilSum < targetUtil:
        taskId = i+1
        i += 1

        period = periodFunc()
        util = utilFunc()
        if utilSum + util > targetUtil:
            util = targetUtil - utilSum
        wcet = util * period
        relativeDeadline = period
        offset = 0

        utilSum += util

        sections = []
        sectionSum = 0
        lastSection = None
        while sectionSum < wcet:
            length = sectionlengthFunc()
            if length > wcet - sectionSum:
                length = wcet - sectionSum
            resourceChoices = list(range(numresources + 1))
            if lastSection is not None:
                resourceChoices.remove(lastSection[0])
            resource = random.choice(resourceChoices)
            lastSection = [resource, length]
            sections.append(lastSection)
            sectionSum += length


        # TODO:
        # Choose the utilization for the task based on the utilization function
        # (you just need to call it - it already has its parameters figured out).
        # If the task's utilization would push it over the target, instead choose
        # its utilization to be the remaining utilization to reach the target sum.

        # Choose task parameters:
        # * offset
        # * period
        # * relative deadline
        # * WCET <-- choose based on utilization and period

        # Build the dictionary for the task parameters
        taskDict = {}
        taskDict[TaskSetJsonKeys.KEY_TASK_ID] = taskId
        taskDict[TaskSetJsonKeys.KEY_TASK_PERIOD] = period
        taskDict[TaskSetJsonKeys.KEY_TASK_WCET] = wcet
        taskDict[TaskSetJsonKeys.KEY_TASK_DEADLINE] = relativeDeadline
        taskDict[TaskSetJsonKeys.KEY_TASK_OFFSET] = offset

        taskDict[TaskSetJsonKeys.KEY_TASK_SECTIONS] = sections

        task = Task(taskDict)
        taskSet.append(task)

    return taskSet


def getResourcecsCeilings(taskset):
    resources = []
    resourceCeilings = {}
    for task in taskset:
        for resource in task.getAllResources():
            if resource not in resources:
                resources.append(resource)
                resourceCeilings[resource] = task.period
            elif resourceCeilings[resource] > task.period:
                resourceCeilings[resource] = task.period
    return resources, resourceCeilings

def rmPIPBlocking(taskset):
    blocking = {}
    resources, resourceCeilings = getResourcecsCeilings(taskset)
    taskset.sort(key = lambda x: (x.period, x.id))
    for i in range(len(taskset)):
        blockingL = 0
        for j in range(i+1, len(taskset)):
            greatest = 0
            for (resource, length) in taskset[j].sections:
                if resource != 0:
                    if resourceCeilings[resource] <= taskset[i].period and length > greatest:
                        greatest = length
            if greatest != 0:
                blockingL += greatest - 1

        blockingS = 0
        for resource in resources:
            greatest = 0
            if resourceCeilings[resource] <= taskset[i].period:
                greatest = 0
                for j in range(i+1, len(taskset)):
                    for section in taskset[j].sections:
                        if section[0] != 0:
                            if section[0] == resource and section[1] > greatest:
                                greatest = section[1]
            if greatest != 0:
                blockingS += greatest - 1

        blocking[i] = min(blockingL, blockingS)

    return blocking

def rmHLPBLocking(taskset):
    blocking = {}
    resources, resourceCeilings = getResourcecsCeilings(taskset)
    taskset.sort(key=lambda x: (x.period, x.id))

    for i in range(len(taskset)):
        greatest = 0
        for j in range(i+1, len(taskset)):
            for (resource, length) in taskset[j].sections:
                if resource != 0:
                    if resourceCeilings[resource] <= taskset[i].period and length > greatest:
                        greatest = length
        blocking[i] = greatest - 1

    return blocking

def rmSchedulabilityTest(taskset, blockingFun):
    blocking = blockingFun(taskset)
    taskset.sort(key=lambda x: (x.period, x.id))

    for i in range(len(taskset)):
        sum = 0
        for j in range(0, i):
            sum += taskset[j].wcet / taskset[j].period
        sum += (taskset[i].wcet + blocking[i]) / taskset[i].period

        if sum > (i+1)*(2**(1/(i+1)) - 1):
            return False

    return True

def rmActualSchedulability(taskset, blockingFun):
    if blockingFun == rmHLPBLocking:
        protocol = 'HLP'
    else:
        protocol = 'PIP'
    #taskset = TaskSet(taskset)

    data = {'startTime':0, 'endTime':10, 'taskset':[]}
    for task in taskset:
        taskdict = {
            "taskId": task.id,
            "period": task.period,
            "wcet": task.wcet,
            "offset": task.offset,
            "sections": task.sections
        }
        data['taskset'].append(taskdict)
    taskset = TaskSet(data)
    rm = rmwithresources.RmScheduler(taskset)
    schedule = rm.buildSchedule(0, 10, protocol)
    return schedule.checkFeasibility()





def checkSchedulability(numTaskSets, targetUtilization, utilFunc, periodFunc, testFunc, numResources, blockingFun):
    """
    Generates numTaskSets task sets using a given utilization-generation function
    and a given period-generation function, such that the task sets have a given
    target system utilization.  Uses the given schedulability test to determine
    what fraction of the task sets are schedulable.

    Returns: the fraction of task sets that pass the schedulability test.
    """
    count = 0
    for i in range(numTaskSets):
        taskSet = generateRandomTaskSet(targetUtilization, utilFunc, periodFunc, numResources)

        if testFunc(taskSet, blockingFun):
            count += 1

    return count / numTaskSets

def performTests(numTests):
    resourseNums = list(range(1, 11))


    results = {'HLP':[], 'PIP':[], 'HLPActual':[], 'PIPActual':[]}
    for resourseNum in resourseNums:
        seed = random.randint(1,1000)
        random.seed(seed)
        HLPResult = checkSchedulability(numTests, 0.7, mediumLightUtilFunc, longPeriodFunc, rmSchedulabilityTest, resourseNum, rmHLPBLocking)

        random.seed(seed)
        PIPResult = checkSchedulability(numTests, 0.7, mediumLightUtilFunc, longPeriodFunc, rmSchedulabilityTest, resourseNum, rmPIPBlocking)

        random.seed(seed)
        HLPActual = checkSchedulability(numTests, 0.7, mediumLightUtilFunc, longPeriodFunc, rmActualSchedulability, resourseNum, rmHLPBLocking)

        random.seed(seed)
        PIPActual = checkSchedulability(numTests, 0.7, mediumLightUtilFunc, longPeriodFunc, rmActualSchedulability, resourseNum, rmPIPBlocking)

        results['HLP'].append(HLPResult)
        results['PIP'].append(PIPResult)
        results['HLPActual'].append(HLPActual)
        results['PIPActual'].append(PIPActual)

    return resourseNums, results

def plotResults(utilVals, results):
    plt.figure()

    LINE_STYLE = ['b:+', 'g-^', 'r-s', 'y-*']

    for (styleId, label) in enumerate(results):
        yvals = results[label]
        plt.plot(utilVals, yvals, LINE_STYLE[styleId], label=label)

        # print("Results for {0}: {1}".format(label, yvals))

    plt.legend(loc="best")

    plt.xlabel("System Utilization")
    plt.ylabel("RM Schedulability")
    plt.title("RM Schedulability for Different Utilization Distributions")

    plt.show()

def testSchedulability():
    random.seed(None) # seed the random library

    # Perform the schedulability tests
    utilVals, results = performTests(100)  #  number, like 1000

    # Plot the results
    plotResults(utilVals, results)

if __name__ == "__main__":
    testSchedulability()

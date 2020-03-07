# SynchronizationProtocols

A program that implements and compares two synchronization protocols - Highest Locker Protocol (HLP) and Priority Inversion Protocol (PIP) - under the Rate Monotonic algorithm. It creates a large number of tasksets and compare each protocol's actual schedulability and schedulability using RM Utility Test.
This program is written for the final Real-Time Systems Project (CS330), taught by Professor Tanya Amert at Carleton College in Winter '20. 

Usage:

python3 schedulability.py -> to see the graph of RM schedulability of HLP and PIP (compared between the protocols and also between their actual schedulability and schedulability according to the RM Utility Test)

python3 rmwithresources.py -> to see the actual schedulability using RM and HLP protocol for a taskset (taskset3.json)


python3 rmwithresources.py jsonFile protocolName(HLP/PIP)

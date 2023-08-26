import asyncio
import v2.DialogHandling.DialogHandler as DialogHandler

loop = asyncio.get_event_loop()
dialog_handler = DialogHandler.DialogHandler()

# import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing
# import v2.DialogHandling.BuiltinNodeDefinitions.CheckSaved as CheckSavedDefinitions
# DialogNodeParsing.register_node_type(CheckSavedDefinitions.CheckSavedLayout)


async def main():
    print("starting main")
    dialog_handler.start_cleaning(loop)
    print("finished awaiting starting cleaning")
    await asyncio.sleep(3)
    print("waited three seconds since starting cleaning")
    # await asyncio.sleep(4)
    # print("stopping cleaning")
    # dialog_handler.stop_cleaning()
    await asyncio.sleep(100)
    return

def stop_loop_on_completion(f):
    print("stop loop")
    loop.stop()

def test_memory_use():
    import sys
    a = stop_loop_on_completion
    b = []
    c = ["asdf"]
    d = "asdf"
    sys.getsizeof(b)
    sys.getsizeof(c)
    sys.getsizeof(d)
    # info on everything loaded into memory
    for var in dir():
        print(var, type(eval(var)), eval(var), sys.getsizeof(eval(var)))

# import yaml
# with open("justMessingWithYaml.yaml") as file:
#     doc_dict = yaml.safe_load_all(file)
#     for yaml_doc in doc_dict:
#         for yaml_node in yaml_doc:
#             print(yaml_node)
#             # if "filters" in yaml_node:
#             #     print(yaml_node["filters"])
#     print("--------------------")
#     print(yaml_doc)
import inspect
# print(inspect.ismodule(DialogHandler))

import src.DialogNodeParsing as parsing
import src.DialogHandler as DialogHandler3
# print("asdf")

node_list = parsing.parse_files("justMessingWithYaml.yaml","v2/revampedReporting.yaml")
# print("back to main testing file, printing out read node info")
# for k,v in node_list.items():
#     print(k,":",vars(v))

'''setting up functions for handler event testing'''
import src.utils.callbackUtils as FI
@FI.callback_settings(allowed=["filter"])
def testfilter_1(active_node, event):
    print(f"callback for testfilter_1 happened, passed in info: active node id {id(active_node)}")
    # raise Exception("testing")
    return True

@FI.callback_settings(allowed=["filter"], has_parameter="optional")
def testfilter_2(active_node, event, args):
    print(f"callback for testfilter_2 happened, passed in info: active node id {id(active_node)}")
    return False

@FI.callback_settings(allowed=["callback"], has_parameter="optional")
def test_optional_parameters(active_node, event, args=None):
    print(f"callback for test_optional_parameters happened, passed in info: active node id {id(active_node)}, args are {args}")

@FI.callback_settings(allowed=["filter","callback"], has_parameter="optional")
def filter_exception(active_node, event, args=None):
    raise Exception("testing")

@FI.callback_settings(allowed=["filter"], has_parameter="always")
def check_from(active_node, event, args):
    print(f"callback for check_from happened, passed in info: active node id {id(active_node)}, args {args}")
    return True

@FI.callback_settings(allowed=["callback"])
async def test_cb1(active_node, event):
    print(f"callback for test_cb1, passed in info: active node id {id(active_node)}")

@FI.callback_settings(allowed=["callback"], has_parameter="always")
def test_cb2(active_node, event, args):
    print(f"callback for test_cb2, passed in info: active node id {id(active_node)}")

@FI.callback_settings(allowed=["transition_filter"])
def ok_to_transition(active_node, event, goal_node):
    print(f"callback for ok_to_transition happened, passed in info: active node id {id(active_node)}, goal {goal_node}")
    return True

@FI.callback_settings(allowed=["transition_callback"], has_parameter="optional")
def test_t_callback_1(active_node, event, goal_node, args=None):
    pass

async def handler_testing():
    h = DialogHandler3.DialogHandler(nodes=node_list, test_var = 5)
    h.register_function(testfilter_1)
    h.register_function(testfilter_2)
    h.register_function(filter_exception)
    h.register_function(check_from)
    h.register_function(test_cb1)
    h.register_function(test_cb2)
    h.register_function(test_optional_parameters)
    h.register_function(ok_to_transition)
    h.register_function(test_t_callback_1)
    h.start_cleaning()
    # h.setup_from_files(["justMessingWithYaml.yaml"])
    print("----------Handlerv3--------")
    print("TESTING KWARGS",h.test_var)
    print("handler loaded graph nodes")
    for k,v in h.graph_nodes.items():
        print("node",k, ": all fields",vars(v))
    # await asyncio.sleep(5)
    print("----------starting a node-----------")
    # h.start_at("nodeA")
    await h.start_at("nodeB", "click", {"start":True})
    print("------active node list")
    for k,v in h.active_nodes.items():
        print("node",f"id <{v.graph_node.id}>",k,vars(v))
    print('------forwarding')
    for event, waiting_list in h.event_forwarding.items():
        print(event, [f"node {id(x)} type <{x.graph_node.TYPE}>:"+str(vars(x)) for x in waiting_list])
    await asyncio.sleep(5)

    print(h.cleaning_task)
    print("------------testing event handling---------------------")
    try:
        await h.notify_event("click",{})
    except Exception as e:
        print(e)

    print("active node list")
    for k,v in h.active_nodes.items():
        print("node",f"id <{v.graph_node.id}>",k,vars(v))

    await asyncio.sleep(10)

    print(h.cleaning_task)
    print("-----------------testing event handling 2---------------")
    await h.notify_event("click",{})

    print("active node list")
    for k,v in h.active_nodes.items():
        print("node",f"id <{v.graph_node.id}>",k,vars(v))

    await asyncio.sleep(5)
    print(h.cleaning_task)
    print("--------active node list hopefully after clean------------------")
    for k,v in h.active_nodes.items():
        print("node",f"id <{v.graph_node.id}>",k,vars(v))


future = asyncio.ensure_future(handler_testing(), loop=loop)
future.add_done_callback(stop_loop_on_completion)
try:
    loop.run_forever()
except KeyboardInterrupt:
    print('Received signal to terminate bot and event loop.')
except Exception as e:
    print(e)
finally:
    future.remove_done_callback(stop_loop_on_completion)
    print('Cleaning up tasks.')

# def test_args(arg1, rest=None):
#     print(arg1, rest)

# test_args(1, "asdf")

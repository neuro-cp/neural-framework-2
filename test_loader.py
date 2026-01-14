from loader.loader import NeuralFrameworkLoader
from observer.observer import BrainObserver

loader = NeuralFrameworkLoader(
    "C:/Users/Admin/Desktop/neural framework"
)

loader.load_neuron_bases()
loader.load_regions()
loader.load_profiles()

brain = loader.compile(
    expression_profile="human_default",
    state_profile="awake",
    compound_profile="experimental_compound"
)

observer = BrainObserver(brain)
observer.summary()
observer.region_details()
observer.connectivity_summary()
observer.validate_references()


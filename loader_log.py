
=== BRAIN SUMMARY ===
Neuron base files loaded: 5
Regions loaded: 45

Regions:
  - a1
  - amyg_base
  - auditory_input
  - bg_base
  - bla
  - brainstem_base
  - ca1
  - ca3
  - cea
  - cerebellar_cortex
  - cerebellum_base
  - cortex
  - cortex_base
  - deep_nuclei
  - dentate_gyrus
  - gpe
  - gpi
  - gustatory_input
  - hip_base
  - insula
  - lgn
  - locus_coeruleus
  - m1
  - md
  - mea
  - medulla
  - mgb
  - pfc
  - pons
  - pulvinar
  - raphe
  - s1
  - sensory_base
  - snc
  - somato_input
  - stn
  - striatum
  - subiculum
  - superior_colliculus
  - thalamus_base
  - v1
  - visual_input
  - vpl
  - vpm
  - vta

Active Profiles:
  Expression: human_default
  State: awake
  Compound: experimental

====================


=== REGION DETAILS ===

[AMYG_BASE]
  No populations defined

[BLA]
  - PYRAMIDAL_CELLS: 350 (excitatory)
  - INTERNEURONS: 120 (inhibitory)
  Total neurons: 470

[CEA]
  - OUTPUT_NEURONS: 200 (inhibitory)
  Total neurons: 200

[MEA]
  - PRINCIPAL_NEURONS: 150 (excitatory)
  Total neurons: 150

[BG_BASE]
  No populations defined

[GPE]
  - OUTPUT_NEURONS: 200 (inhibitory)
  Total neurons: 200

[GPI]
  - OUTPUT_NEURONS: 250 (inhibitory)
  Total neurons: 250

[SNC]
  - DOPAMINERGIC_NEURONS: 180 (neuromodulatory)
  Total neurons: 180

[STN]
  - EXCITATORY_NEURONS: 150 (excitatory)
  Total neurons: 150

[STRIATUM]
  - D1_MSN: 400 (inhibitory)
  - D2_MSN: 400 (inhibitory)
  - INTERNEURONS: 150 (inhibitory)
  Total neurons: 950

[BRAINSTEM_BASE]
  No populations defined

[LOCUS_COERULEUS]
  - NORADRENERGIC_NEURONS: 150 (excitatory)
  Total neurons: 150

[MEDULLA]
  - AUTONOMIC_NEURONS: 250 (autonomic)
  Total neurons: 250

[PONS]
  - MIXED_NEURONS: 300 (mixed)
  Total neurons: 300

[RAPHE]
  - SEROTONERGIC_NEURONS: 250 (neuromodulatory)
  Total neurons: 250

[VTA]
  - DOPAMINERGIC_NEURONS: 200 (neuromodulatory)
  - GABA_INTERNEURONS: 80 (inhibitory)
  Total neurons: 280

[CEREBELLAR_CORTEX]
  - GRANULE_CELLS: 2000 (excitatory)
  - PURKINJE_CELLS: 150 (inhibitory)
  - INTERNEURONS: 300 (inhibitory)
  Total neurons: 2450

[CEREBELLUM_BASE]
  No populations defined

[CORTEX]
  - GRANULE_CELLS: 2000 (excitatory)
  - PURKINJE_CELLS: 150 (inhibitory)
  - INTERNEURONS: 300 (inhibitory)
  Total neurons: 2450

[DEEP_NUCLEI]
  - OUTPUT_NEURONS: 200 (excitatory)
  Total neurons: 200

[A1]
  - L4_EXCITATORY: 750 (excitatory)
  - L2_3_PYRAMIDAL: 850 (excitatory)
  - INTERNEURONS: 380 (inhibitory)
  Total neurons: 1980

[CORTEX_BASE]
  No populations defined

[INSULA]
  - L2_3_PYRAMIDAL: 600 (excitatory)
  - L5_PYRAMIDAL: 450 (excitatory)
  - INTERNEURONS: 300 (inhibitory)
  Total neurons: 1350

[M1]
  - L2_3_PYRAMIDAL: 700 (excitatory)
  - L5_PYRAMIDAL: 600 (excitatory)
  - INTERNEURONS: 350 (inhibitory)
  Total neurons: 1650

[PFC]
  - L2_3_PYRAMIDAL: 950 (excitatory)
  - L5_PYRAMIDAL: 700 (excitatory)
  - INTERNEURONS: 450 (inhibitory)
  Total neurons: 2100

[S1]
  - L4_EXCITATORY: 850 (excitatory)
  - L2_3_PYRAMIDAL: 900 (excitatory)
  - INTERNEURONS: 400 (inhibitory)
  Total neurons: 2150

[V1]
  - L4_EXCITATORY: 800 (excitatory)
  - L2_3_PYRAMIDAL: 1000 (excitatory)
  - L5_PYRAMIDAL: 600 (excitatory)
  - INTERNEURONS: 400 (inhibitory)
  Total neurons: 2800

[CA1]
  - PYRAMIDAL_CELLS: 450 (excitatory)
  - INTERNEURONS: 100 (inhibitory)
  Total neurons: 550

[CA3]
  - PYRAMIDAL_CELLS: 500 (excitatory)
  - INTERNEURONS: 120 (inhibitory)
  Total neurons: 620

[DENTATE_GYRUS]
  - GRANULE_CELLS: 1000 (excitatory)
  - INTERNEURONS: 150 (inhibitory)
  Total neurons: 1150

[HIP_BASE]
  No populations defined

[SUBICULUM]
  - PYRAMIDAL_CELLS: 300 (excitatory)
  Total neurons: 300

[AUDITORY_INPUT]
  No populations defined

[GUSTATORY_INPUT]
  No populations defined

[SENSORY_BASE]
  No populations defined

[SOMATO_INPUT]
  No populations defined

[VISUAL_INPUT]
  No populations defined

[LGN]
  - RELAY_NEURONS: 600 (excitatory)
  Total neurons: 600

[MD]
  - RELAY_NEURONS: 700 (excitatory)
  Total neurons: 700

[MGB]
  - RELAY_NEURONS: 500 (excitatory)
  Total neurons: 500

[PULVINAR]
  - RELAY_NEURONS: 800 (excitatory)
  Total neurons: 800

[SUPERIOR_COLLICULUS]
  - SUPERFICIAL_VISUAL: 500 (excitatory)
  - DEEP_MOTOR: 400 (excitatory)
  - INTERNEURONS: 300 (inhibitory)
  Total neurons: 1200

[THALAMUS_BASE]
  No populations defined

[VPL]
  - RELAY_NEURONS: 600 (excitatory)
  - INTERNEURONS: 150 (inhibitory)
  Total neurons: 750

[VPM]
  - RELAY_NEURONS: 500 (excitatory)
  Total neurons: 500

======================


=== CONNECTIVITY SUMMARY ===

[BLA]
  Inputs:
    <- HIPPOCAMPAL_FORMATION (strength 0.4)
    <- CORTEX (strength 0.5)
  Outputs:
    -> CORTEX (strength 0.4)
    -> CEA (strength 0.7)

[CEA]
  Outputs:
    -> BRAINSTEM (strength 0.8)

[GPE]
  Outputs:
    -> STN (strength 0.8)

[GPI]
  Outputs:
    -> THALAMUS (strength 1.0)

[STN]
  Outputs:
    -> GPi (strength 0.9)

[STRIATUM]
  Inputs:
    <- CORTEX (strength 0.6)
    <- HIPPOCAMPAL_FORMATION (strength 0.3)
    <- AMYGDALA (strength 0.4)
    <- BRAINSTEM (strength 1.0)
  Outputs:
    -> GPi (strength 0.7)
    -> GPe (strength 0.7)

[LOCUS_COERULEUS]
  Outputs:
    -> CORTEX (strength 0.3)
    -> THALAMUS (strength 0.4)
    -> HIPPOCAMPUS (strength 0.3)
    -> BASAL_GANGLIA (strength 0.2)

[VTA]
  Outputs:
    -> BASAL_GANGLIA (strength 1.0)
    -> CORTEX (strength 0.6)
    -> HIPPOCAMPAL_FORMATION (strength 0.4)

[CEREBELLAR_CORTEX]
  Inputs:
    <- CORTEX (strength 0.6)
    <- BRAINSTEM (strength 1.0)
  Outputs:
    -> DEEP_NUCLEI (strength 1.0)

[CORTEX]
  Inputs:
    <- CORTEX (strength 0.6)
    <- BRAINSTEM (strength 1.0)
  Outputs:
    -> DEEP_NUCLEI (strength 1.0)

[DEEP_NUCLEI]
  Inputs:
    <- CEREBELLAR_CORTEX (strength 1.0)
  Outputs:
    -> THALAMUS (strength 0.8)
    -> BRAINSTEM (strength 0.6)

[A1]
  Inputs:
    <- MGB (strength 1.0)
  Outputs:
    -> CORTEX (strength 0.6)
    -> PULVINAR (strength 0.3)

[PFC]
  Inputs:
    <- MD (strength 0.7)
    <- HIPPOCAMPAL_FORMATION (strength 0.4)
  Outputs:
    -> MD (strength 0.6)

[V1]
  Inputs:
    <- LGN (strength 0.9)
  Outputs:
    -> CORTEX (strength 0.7)
    -> PULVINAR (strength 0.45)
    -> V1 (strength 0.15)

[CA1]
  Inputs:
    <- CA3 (strength 0.8)
    <- CORTEX (strength 0.4)
  Outputs:
    -> SUBICULUM (strength 0.9)

[CA3]
  Inputs:
    <- DENTATE_GYRUS (strength 0.9)
  Outputs:
    -> CA1 (strength 0.8)

[DENTATE_GYRUS]
  Outputs:
    -> CA3 (strength 0.8)

[SUBICULUM]
  Inputs:
    <- CA1 (strength 0.9)
  Outputs:
    -> CORTEX (strength 0.6)
    -> BLA (strength 0.4)

[AUDITORY_INPUT]
  Outputs:
    -> MGB (strength 1.0)

[GUSTATORY_INPUT]
  Outputs:
    -> THALAMUS (strength 1.0)

[SOMATO_INPUT]
  Outputs:
    -> THALAMUS (strength 1.0)

[VISUAL_INPUT]
  Outputs:
    -> THALAMUS (strength 1.0)

[LGN]
  Outputs:
    -> V1 (strength 1.0)
    -> PULVINAR (strength 0.4)

[MD]
  Inputs:
    <- PFC (strength 0.6)
  Outputs:
    -> PFC (strength 0.7)

[MGB]
  Inputs:
    <- AUDITORY_INPUT (strength 1.0)
  Outputs:
    -> A1 (strength 1.0)

[PULVINAR]
  Outputs:
    -> V1 (strength 0.8)
    -> S1 (strength 0.4)

[SUPERIOR_COLLICULUS]
  Inputs:
    <- LGN (strength 0.6)
    <- V1 (strength 0.4)
  Outputs:
    -> PULVINAR (strength 0.5)
    -> LGN (strength 0.3)

[VPL]
  Inputs:
    <- SENSORY_INTERFACES (strength 1.0)
    <- CORTEX (strength 0.4)
  Outputs:
    -> CORTEX (strength 0.9)

============================


=== REFERENCE VALIDATION ===

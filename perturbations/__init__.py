from perturbations.base import BasePerturbation
from perturbations.chunk_shuffle import ChunkShufflePerturbation
from perturbations.conflicting import ConflictingEvidencePerturbation
from perturbations.distractor import DistractorInjectionPerturbation
from perturbations.history_contamination import HistoryContaminationPerturbation
from perturbations.instruction_burial import InstructionBurialPerturbation
from perturbations.paraphrase import ParaphraseEvidencePerturbation

from core.models import PerturbationType

_REGISTRY: dict[str, BasePerturbation] = {
    PerturbationType.CHUNK_SHUFFLE: ChunkShufflePerturbation(),
    PerturbationType.DISTRACTOR_INJECTION: DistractorInjectionPerturbation(),
    PerturbationType.CONFLICTING_EVIDENCE: ConflictingEvidencePerturbation(),
    PerturbationType.INSTRUCTION_BURIAL: InstructionBurialPerturbation(),
    PerturbationType.HISTORY_CONTAMINATION: HistoryContaminationPerturbation(),
    PerturbationType.PARAPHRASE_EVIDENCE: ParaphraseEvidencePerturbation(),
}


def get_perturbation(perturbation_type: PerturbationType) -> BasePerturbation:
    if perturbation_type not in _REGISTRY:
        raise ValueError(f"Unknown perturbation type: {perturbation_type}")
    return _REGISTRY[perturbation_type]


__all__ = [
    "BasePerturbation",
    "get_perturbation",
    "ChunkShufflePerturbation",
    "DistractorInjectionPerturbation",
    "ConflictingEvidencePerturbation",
    "InstructionBurialPerturbation",
    "HistoryContaminationPerturbation",
    "ParaphraseEvidencePerturbation",
]

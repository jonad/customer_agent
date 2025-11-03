from .sub_agents import CategorizerAgent, ResponderAgent
from google.adk.agents import SequentialAgent


class CustomerAgentOrchestrator:
    def __init__(self):
        # Root Agent
        self.root_agent = SequentialAgent(
            name="CustomerInquiryProcessorPipeline",
            sub_agents=[CategorizerAgent, ResponderAgent],
            description="A pipeline that processes customer inquiries by categorizing them and generating appropriate pre-defined responses",
        )

from crewai import Crew, Process
from agents import coordinator_agent, travel_info_agent, local_recommendation_agent
from tasks import initial_travel_plan_task, local_recommendation_task, final_coordinator_task

class TravelCoordinatorCrew():

    def crew(self) -> Crew:  # Crew 객체 생성 반환
        return Crew(
            agents=[travel_info_agent, local_recommendation_agent,coordinator_agent],
            tasks=[initial_travel_plan_task, local_recommendation_task, final_coordinator_task],
            process=Process.sequential,  # 순차적 실행 => (중요) task 순서대로 실행
            verbose=True   # 실제 서비스에서는 False로 설정
        )


